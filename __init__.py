# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Texture Compactor",
    "author": "Mike Pan",
    "description": "Optimize textures to reduce memory usage during render",
    "blender": (4, 0, 0),
    "version": (0, 0, 1),
    "location": "Properties > Scene > Texture Compactor",
    "warning": "",
    "category": "Render",
}

import bpy

from texturecompactor import ui
from texturecompactor import core


classes = (
    ui.TEXTURECOMPACTOR_PT_main_panel,
    ui.TEXTURECOMPACTOR_OT_scan_textures,
    ui.TEXTURECOMPACTOR_OT_optimize_textures,
    ui.TEXTURECOMPACTOR_OT_show_report,
)


@bpy.app.handlers.persistent
def clear_addon_data(dummy):
    # Clear or reset your addon data here
    print("New file loaded, clearing addon data...")
    bpy.context.scene.TC_texture_metadata.clear()
    bpy.context.scene.TC_texture_metadata = []


def register():
    bpy.app.handlers.load_post.append(clear_addon_data)

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.TC_convert_greyscale = bpy.props.EnumProperty(
        items=[
            ("0", "Off", "Do nothing"),
            ("1", "Safe", "Optimize when there is no visible difference"),
            ("2", "Aggressive", "Use a higher tolerance, might make less colorful textures greyscale"),
        ],
        name="Convert to Greyscale",
        default="1",
        options=set(),
        update=core.update_memory_usage,
    )

    bpy.types.Scene.TC_smart_resize = bpy.props.EnumProperty(
        items=[
            ("0", "Off", "Do nothing"),
            ("1", "Safe", "Optimize when there is no visible difference"),
            ("2", "Aggressive", "Use a higher tolerance to find more textures that can be resized safely"),
        ],
        name="Smart Resize",
        default="1",
        options=set(),
        update=core.update_memory_usage,
    )

    bpy.types.Scene.TC_optimize_float = bpy.props.EnumProperty(
        items=[
            ("0", "Off", "Do nothing"),
            ("1", "Safe", "Set all float texture to be read at half-precision (16-bit)"),
            ("2", "Aggressive", "Try to convert greyscale float textures to 16-bit integers"),
        ],
        name="Float Textures",
        default="1",
        options=set(),
        update=core.update_memory_usage,
    )

    bpy.types.Scene.TC_texture_swap = bpy.props.EnumProperty(
        items=[("0", "Original", "Use original textures"), ("1", "Optimized", "Use optimized textures")],
        name="Switch Textures",
        options=set(),
        default="0",
    )

    bpy.types.Scene.TC_texture_metadata = []


def unregister():
    bpy.app.handlers.load_post.remove(clear_addon_data)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.TC_convert_greyscale
    del bpy.types.Scene.TC_smart_resize
    del bpy.types.Scene.TC_optimize_float
    del bpy.types.Scene.TC_texture_swap
    del bpy.types.Scene.TC_texture_metadata


if __name__ == "__main__":
    register()
