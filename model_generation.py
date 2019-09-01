#!/usr/bin/python3.5
from __future__ import print_function
import csv
import bpy
import os
import numpy as np
from mathutils import Vector
import math
import bmesh
from svgpathtools import Path, Line, QuadraticBezier, CubicBezier, Arc, parse_path, svg2paths,svg2paths2, wsvg, kinks, smoothed_path
from ruamel import yaml
from pathlib import Path


class SvgPath():
    """
    svg_file: Absolute path for the svg file
    """
    def __init__(self, svg_file):
        self.filepath = svg_file
        self.loadSvg()

    def loadSvg(self):
        paths, attributes, svg_attributes = svg2paths2(self.filepath)
        self.view_box = svg_attributes['viewBox'].split(" ")
        # min_x min_y max_x max_y
        for index, item in enumerate(self.view_box):
            self.view_box[index] = float(item)
        self.view_box_height = self.view_box[-1]
        self.view_box_width = self.view_box[-2]
        if len(paths) > 0:
            self.path = paths[0]
        else:
            print("Hey, your svg file does not have path elements!")
        self.length = self.path.length()
        self.knot_nums = len(self.path)

class CurveGeneration():
    """
    This holds the curve_obj
    """
    def __init__(self):
        print ("Curve Generation Init")
        self.clearCurves()
        # bezier curve preset
        self.curve_data = bpy.data.curves.new('track', type='CURVE')
        self.curve_data.dimensions = '2D'
        self.curve_obj = bpy.data.objects.new('track', self.curve_data)
        bpy.context.scene.objects.link(self.curve_obj)
        self.curve_length = 0

    """
    :svg_path  must be SvgPath() class type
    """
    def createFromSvg(self, svg_path):
        # when use different loading method to construct the bezier curve,
        # the old curve need to removed provent old control points
        self.curve_data.splines.clear()
        self.curve_length = svg_path.length
        # update self.bezier_curve handle
        self.bezier_curve = self.curve_data.splines.new('BEZIER')
        # define the knots size
        self.bezier_curve.bezier_points.add(svg_path.knot_nums-1)
        # fill the knots and handle points(control points)
        for i in range(len(self.bezier_curve.bezier_points)):
            x = svg_path.path[i].start.real
            # you have to flip y axis to get it displayed right
            y = (svg_path.view_box_height - svg_path.path[i].start.imag)
            ## knot
            self.bezier_curve.bezier_points[i].co = Vector((x, y, 0))
            ## left handle
            if i == 0:
                self.bezier_curve.bezier_points[i].handle_left = Vector((x, y, 0))
            else:
                x = svg_path.path[i-1].control2.real
                y = (svg_path.view_box_height - svg_path.path[i-1].control2.imag)
                self.bezier_curve.bezier_points[i].handle_left = Vector((x, y, 0))
            ## right handle
            if len(svg_path.path[i]) == 2:
                self.bezier_curve.bezier_points[i].handle_right = self.bezier_curve.bezier_points[i].co
            else:
                x = svg_path.path[i].control1.real
                y = (svg_path.view_box_height - svg_path.path[i].control1.imag)
                self.bezier_curve.bezier_points[i].handle_right = Vector((x, y, 0))
        self.setOriginToStartPoint()

    def createFromCsv(self, data_frame):
        print ("createFromCsv() place holder, to implement")


    def setOriginToStartPoint(self):
        self.start_point = self.bezier_curve.bezier_points[0].co
        self.curve_obj.select = True
        scene = bpy.context.scene
        scene.objects.active = self.curve_obj
        saved_location = scene.cursor_location.copy()
        # precise selection in edit mode
        if self.curve_obj.mode == 'OBJECT':
            bpy.ops.object.editmode_toggle()
        self.bezier_curve.bezier_points[0].select_control_point = True
        # snap cursor to selection
        print("print cursor location:", scene.cursor_location)
        scene.cursor_location = self.start_point
        if self.curve_obj.mode == 'EDIT':
            bpy.ops.object.editmode_toggle()
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        scene.cursor_location = saved_location

    def clearCurves(self):
        '''
        clean scene object and data to prevent suffix
        '''
        # unlink only mesh type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type=='MESH':
                    scene.objects.unlink(obj)

        # delete only mesh type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'MESH':
                    obj.select = True
                    bpy.ops.object.delete()

        # delete mesh data
        for block in bpy.data.meshes:
            bpy.data.meshes.remove(block, do_unlink=True)

        # unlink only curve type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type=='CURVE':
                    scene.objects.unlink(obj)
        # delete only curve type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'CURVE':
                    obj.select = True
                    bpy.ops.object.delete()
        # clean
        for block in bpy.data.curves:
            bpy.data.curves.remove(block, do_unlink=True)


class RoadBaseMesh():
    def __init__(self, width, length, location):
        self.file_name = "dash.png"
        self.working_directory = Path.cwd()
        self.road_width = width
        self.base_mesh_length = length
        self.clearMeshes()
        bpy.ops.mesh.primitive_plane_add(location=(0,0,0))
        # get the object handle by active context
        self.road_obj = bpy.context.active_object
        self.reShapeBaseMesh()
        bpy.ops.image.open(filepath=self.file_name,directory=str(self.working_directory.joinpath('resources')),files=[{"name":self.file_name}])
        self.image_dash = bpy.data.images[self.file_name]
        self.reShapeBaseMesh()
        self.linkTexture()
        self.moveToLocation(location)

    def reShapeBaseMesh(self):
        '''
        the vertex oder of the rectangle mesh in local frame
        [2]---[3]
         |     |
        [0]---[1]
        '''
        self.road_obj.data.vertices[0].co = [0, -self.road_width/2.0, 0]
        self.road_obj.data.vertices[1].co = [self.base_mesh_length, -self.road_width/2.0, 0]
        self.road_obj.data.vertices[2].co = [0, self.road_width/2.0, 0]
        self.road_obj.data.vertices[3].co = [self.base_mesh_length, self.road_width/2.0, 0]

    def myActivator(self):
        bpy.context.scene.objects.active = self.road_obj

    def moveToLocation(self, location):
        self.myActivator()
        self.road_obj.location = location

    def linkTexture(self):
        self.myActivator()
        self.mesh_data =bpy.context.object.data
        uv_texture = self.mesh_data.uv_textures.new("texture")
        uv_layer = self.mesh_data.uv_layers[-1].data

        vert_uvs = [[0,0], [1, 0], [0, 1], [1,1]]
        self.mesh_data.uv_layers[-1].data.foreach_set("uv", [uv for pair in [vert_uvs[l.vertex_index] for l in self.mesh_data.loops] for uv in pair])

        for uv_tex_face in self.mesh_data.uv_textures.active.data:
            uv_tex_face.image = self.image_dash

    def clearMeshes(self):
        '''
        clear scene object and data to prevent suffix
        '''
        # unlink only mesh type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type=='MESH':
                    scene.objects.unlink(obj)

        # delete only mesh type
        for scene in bpy.data.scenes:
            for obj in scene.objects:
                if obj.type == 'MESH':
                    obj.select = True
                    bpy.ops.object.delete()

        # delete mesh data
        for block in bpy.data.meshes:
            bpy.data.meshes.remove(block, do_unlink=True)


class RoadGeneration():
    def __init__(self, curve, road_width):
        """
        :curve: CurveGeneration() curve class object
        """
        self.road_width = road_width
        self.curve = curve
        self.road_base_length = curve.curve_length / int(curve.curve_length)
        self.start_location = curve.start_point
        self.road = RoadBaseMesh(self.road_width, self.road_base_length, self.start_location)
        self.deformationModifier()
        self.saveWavefrontObj()

    def deformationModifier(self):
        bpy.context.scene.objects.active = self.road.road_obj
        # copies
        bpy.ops.object.modifier_add(type='ARRAY')
        bpy.context.object.modifiers["Array"].relative_offset_displace[0]=1
        bpy.context.object.modifiers["Array"].fit_type='FIT_LENGTH'
        bpy.context.object.modifiers["Array"].fit_length=self.curve.curve_length-self.road.base_mesh_length
        bpy.context.object.modifiers["Array"].curve=self.curve.curve_obj
        # along the curve
        bpy.ops.object.modifier_add(type='CURVE')
        bpy.context.object.modifiers["Curve"].object=self.curve.curve_obj
        # apply modifiers
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Array")
        bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Curve")

    def saveWavefrontObj(self):
        self.road.road_obj.select = True
        file_path = str(self.road.working_directory.joinpath('generated').joinpath('road.obj'))
        bpy.ops.export_scene.obj(filepath=file_path,path_mode='COPY')

svg_path= SvgPath('data/drawing-test.svg')
# blender curve
curve = CurveGeneration()
curve.createFromSvg(svg_path)
road = RoadGeneration(curve, 4)
