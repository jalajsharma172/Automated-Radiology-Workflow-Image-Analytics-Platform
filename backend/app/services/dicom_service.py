import pydicom
import numpy as np
from PIL import Image
import io

def extract_dicom_metadata(file_like_obj) -> dict:
    """
    Extracts high-level DICOM header metadata without loading pixel arrays.
    """
    try:
        # Read only header tags for performance
        ds = pydicom.dcmread(file_like_obj, stop_before_pixels=True)
        
        # Check standard properties
        modality = getattr(ds, "Modality", "Unknown")
        rows = getattr(ds, "Rows", 0)
        columns = getattr(ds, "Columns", 0)
        
        # Extract number of frames (multi-frame, common in SEG)
        num_frames = int(getattr(ds, "NumberOfFrames", 1))
        
        # Check segment count for SEG files
        num_segments = 0
        segment_labels = []
        if hasattr(ds, "SegmentSequence"):
            num_segments = len(ds.SegmentSequence)
            for seg in ds.SegmentSequence:
                label = getattr(seg, "SegmentLabel", f"Segment {getattr(seg, 'SegmentNumber', '')}")
                segment_labels.append(label)
        
        metadata = {
            "patient_id": getattr(ds, "PatientID", "Unknown"),
            "study_date": getattr(ds, "StudyDate", "Unknown"),
            "modality": modality,
            "series_description": getattr(ds, "SeriesDescription", "No Description"),
            "rows": rows,
            "columns": columns,
            "number_of_frames": num_frames,
            "num_segments": num_segments,
            "segment_labels": segment_labels
        }
        return metadata
    except Exception as e:
        return {
            "error": f"Failed to extract DICOM metadata: {str(e)}",
            "modality": "Unknown",
            "number_of_frames": 1
        }

def render_dicom_to_png(file_like_obj, frame_index: int = 0) -> io.BytesIO:
    """
    Reads DICOM file, extracts pixel array, normalizes it, and saves a specific frame as PNG.
    """
    ds = pydicom.dcmread(file_like_obj)
    
    if not hasattr(ds, "pixel_array"):
        raise ValueError("DICOM file does not contain a pixel array")
        
    pixel_array = ds.pixel_array
    
    # 1. Handle Multi-frame (3D shapes like (frames, rows, cols))
    if len(pixel_array.shape) == 3:
        num_frames = pixel_array.shape[0]
        # Clamp frame_index within range
        frame_index = max(0, min(frame_index, num_frames - 1))
        pixel_array = pixel_array[frame_index]
    elif len(pixel_array.shape) == 2:
        # 2D slice
        pass
    else:
        raise ValueError(f"Unsupported pixel array dimensions: {pixel_array.shape}")
        
    # 2. Rescale CT Hounsfield Units if tags exist
    if hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept"):
        pixel_array = pixel_array * ds.RescaleSlope + ds.RescaleIntercept
        
    # 3. Normalize values to 0-255 for image display
    p_min = float(pixel_array.min())
    p_max = float(pixel_array.max())
    
    if p_max - p_min > 0:
        normalized = (pixel_array - p_min) / (p_max - p_min) * 255.0
    else:
        normalized = np.zeros_like(pixel_array)
        
    normalized = normalized.astype(np.uint8)
    
    # 4. Generate Image based on Modality
    modality = getattr(ds, "Modality", "Unknown")
    
    if modality == "SEG":
        # Segmentation files are binary overlays.
        # We output a transparent red overlay PNG (Tailwind Red 500 equivalent) so the browser can stack it
        h, w = normalized.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[normalized > 0] = [239, 68, 68, 175] # Red overlay with ~70% opacity
        img = Image.fromarray(rgba, mode="RGBA")
    elif modality == "PT":
        # PET scans. Standard hot colormap is hard in pure python, but we can do a grayscale or a warm orange colormap
        # Let's write a fast orange/fire colormap conversion for premium look
        h, w = normalized.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        # Create a fire/hot mapping: R gets normalized directly, G gets normalized * 0.5, B is 0
        # This gives a beautiful warm red/orange/yellow heatmap!
        rgba[..., 0] = normalized # Red channel
        rgba[..., 1] = (normalized * 0.7).astype(np.uint8) # Green channel
        rgba[..., 2] = (normalized * 0.2).astype(np.uint8) # Blue channel
        rgba[..., 3] = 255 # Opacity channel
        img = Image.fromarray(rgba, mode="RGBA")
    else:
        # Default grayscale image for CT and others
        img = Image.fromarray(normalized, mode="L")
        
    # 5. Save to image stream
    out_io = io.BytesIO()
    img.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io


def resample_grid(src_array, src_origin, src_spacing, dest_origin, dest_spacing, dest_shape):
    """
    Resamples src_array (2D) to match the coordinate grid of dest.
    """
    dest_rows, dest_cols = dest_shape
    
    # Generate dest grid of physical coordinates
    col_coords = dest_origin[0] + np.arange(dest_cols) * dest_spacing[0]
    row_coords = dest_origin[1] + np.arange(dest_rows) * dest_spacing[1]
    
    # Map physical coordinates to src pixel coordinates
    src_col_idx = (col_coords - src_origin[0]) / src_spacing[0]
    src_row_idx = (row_coords - src_origin[1]) / src_spacing[1]
    
    # Meshgrid of src pixel coordinates
    cols_grid, rows_grid = np.meshgrid(src_col_idx, src_row_idx)
    
    h, w = src_array.shape
    
    # Bilinear interpolation boundaries
    r0 = np.floor(rows_grid).astype(np.int32)
    r1 = r0 + 1
    c0 = np.floor(cols_grid).astype(np.int32)
    c1 = c0 + 1
    
    # Clip indices to stay within bounds
    r0_c = np.clip(r0, 0, h - 1)
    r1_c = np.clip(r1, 0, h - 1)
    c0_c = np.clip(c0, 0, w - 1)
    c1_c = np.clip(c1, 0, w - 1)
    
    # Weights
    wa = (r1 - rows_grid) * (c1 - cols_grid)
    wb = (r1 - rows_grid) * (cols_grid - c0)
    wc = (rows_grid - r0) * (c1 - cols_grid)
    wd = (rows_grid - r0) * (cols_grid - c0)
    
    # Interpolate
    interpolated = (wa * src_array[r0_c, c0_c] +
                    wb * src_array[r0_c, c1_c] +
                    wc * src_array[r1_c, c0_c] +
                    wd * src_array[r1_c, c1_c])
                    
    # Zero out pixels that fall outside the src bounds
    outside = (rows_grid < 0) | (rows_grid > h - 1) | (cols_grid < 0) | (cols_grid > w - 1)
    interpolated[outside] = 0.0
    
    return interpolated


def render_resampled_pet_slice(pet_stream, ct_stream) -> io.BytesIO:
    """
    Reads PET and CT, resamples PET slice to match CT pixel resolution and bounding box,
    colorizes it with a fire colormap, and returns a transparent PNG stream.
    """
    ds_pet = pydicom.dcmread(pet_stream)
    ds_ct = pydicom.dcmread(ct_stream)
    
    pet_array = ds_pet.pixel_array.astype(np.float32)
    
    # Extract coordinate systems
    pet_origin = [float(val) for val in ds_pet.ImagePositionPatient[:2]]
    pet_spacing = [float(val) for val in ds_pet.PixelSpacing]
    
    ct_origin = [float(val) for val in ds_ct.ImagePositionPatient[:2]]
    ct_spacing = [float(val) for val in ds_ct.PixelSpacing]
    ct_shape = (ds_ct.Rows, ds_ct.Columns)
    
    # Resample
    resampled = resample_grid(pet_array, pet_origin, pet_spacing, ct_origin, ct_spacing, ct_shape)
    
    # Normalize to 0-255
    p_min = resampled.min()
    p_max = resampled.max()
    if p_max - p_min > 0:
        normalized = (resampled - p_min) / (p_max - p_min) * 255.0
    else:
        normalized = np.zeros_like(resampled)
    normalized = normalized.astype(np.uint8)
    
    # Map to RGBA warm orange/fire colormap
    h, w = normalized.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    
    # Fire mapping
    rgba[..., 0] = normalized # Red
    rgba[..., 1] = (normalized * 0.7).astype(np.uint8) # Green
    rgba[..., 2] = (normalized * 0.2).astype(np.uint8) # Blue
    
    # Transparency: make background pixels transparent (e.g. threshold 10)
    rgba[..., 3] = np.where(normalized > 10, 200, 0) # semi-opaque for active hot spots
    
    img = Image.fromarray(rgba, mode="RGBA")
    
    out_io = io.BytesIO()
    img.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io


def render_resampled_seg_slice(seg_stream, frame_index: int, ct_stream) -> io.BytesIO:
    """
    Reads SEG and CT, resamples target SEG frame to match CT coordinate grid,
    renders it as a transparent red overlay PNG.
    """
    ds_seg = pydicom.dcmread(seg_stream)
    ds_ct = pydicom.dcmread(ct_stream)
    
    # Extract SEG frame pixels
    seg_array = ds_seg.pixel_array[frame_index].astype(np.float32)
    
    # Extract coordinate systems
    frame_pos = ds_seg.PerFrameFunctionalGroupsSequence[frame_index].PlanePositionSequence[0].ImagePositionPatient
    seg_origin = [float(val) for val in frame_pos[:2]]
    
    pixel_measures = ds_seg.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence[0]
    seg_spacing = [float(val) for val in pixel_measures.PixelSpacing]
    
    ct_origin = [float(val) for val in ds_ct.ImagePositionPatient[:2]]
    ct_spacing = [float(val) for val in ds_ct.PixelSpacing]
    ct_shape = (ds_ct.Rows, ds_ct.Columns)
    
    # Resample
    resampled = resample_grid(seg_array, seg_origin, seg_spacing, ct_origin, ct_spacing, ct_shape)
    
    # Create semi-transparent red overlay where mask > 0.5
    h, w = resampled.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    
    mask = resampled > 0.5
    rgba[mask] = [239, 68, 68, 175] # Red overlay (Tailwind Red 500)
    
    img = Image.fromarray(rgba, mode="RGBA")
    
    out_io = io.BytesIO()
    img.save(out_io, format="PNG")
    out_io.seek(0)
    return out_io
