from . import settings
import bpy
import hashlib
import os


def optimize(img_info):
    image = img_info.image

    if img_info.optimized_resolution:
        width = image.size[0]
        height = image.size[1]

        new_width = max(2, img_info.optimized_resolution[0])
        new_height = max(2, img_info.optimized_resolution[1])

        image.scale(new_width, new_height)
        print(f"Resized {image.name} to {new_width}x{new_height}")

    elif img_info.optimized_depth:
        # Save the original settings
        colorspace_original = image.colorspace_settings.name
        image.colorspace_settings.name = "Non-Color"

        # set up new file path
        filepath_original = image.filepath_raw
        ext = filepath_original.split(".")[-1]

        # hash the filepath to avoid conflicts of multiple images with the same name like albedo.png
        hash_object = hashlib.md5(filepath_original.encode())
        hashed_filepath = hash_object.hexdigest()

        # Set the folder path for optimized images
        folder_path = os.path.join(os.path.dirname(bpy.data.filepath), "tc_optimized")

        # Create the folder if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)

        # new file path
        filepath_new = os.path.join(folder_path, f"{hashed_filepath}.png")
       

        scene = bpy.context.scene
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.compression = 15
        scene.render.image_settings.color_depth = "8"

        if img_info.optimized_depth == 8:
            scene.render.image_settings.color_mode = "BW"
        elif img_info.optimized_depth == 24:
            scene.render.image_settings.color_mode = "RGB"
        else:
            raise (f"Invalid depth {img_info.optimized_depth} for {image.name}")

        image.save_render(bpy.path.abspath(filepath_new), scene=scene)

        # replace image with new file
        print(f"Using 8bit {image.name}")
        
        image.filepath_raw = bpy.path.relpath(filepath_new)
        
        image.colorspace_settings.name = colorspace_original

        img_info.optimized_path = filepath_new

        img_info.image.reload()


def convert_to_dxt1(image):
    """Convert the given image to DXT1 format using crunch.exe."""
    # get file extension of filepath
    filepath_original = image.filepath_raw
    ext = filepath_original.split(".")[-1]
    # deal with library assets
    filepath_original = bpy.path.abspath(filepath_original, library=image.library)

    cmd = [
        settings.crunch_path,
        "-file",
        filepath_original,
        "-out",
        filepath_original + ".dds",
        "-fileformat",
        "dds",
        "-dxt1",
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error compressing {image.name}: {result.stderr}")
        return False

    # Replace image with new file
    image.filepath_raw = filepath_original + ".dds"

    return True


def use_original(image_list):
    print("Using original images")
    for img in image_list:
        if img.original_path:
            img.image.filepath_raw = img.original_path
            img.image.reload()


def use_optimized(image_list):
    print("Using optimized images")
    for img in image_list:
        if img.optimized_path:
            img.image.filepath_raw = img.optimized_path
            img.image.reload()
