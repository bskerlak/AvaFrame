import logging

from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger("com1DFA")

AVAFRAME_SCHEMA = pa.schema([
    pa.field("anriss", pa.string(), nullable=False),
    pa.field("relTh", pa.float32(), nullable=False),
    pa.field("mu", pa.float32(), nullable=False),
    pa.field("xsi", pa.int16(), nullable=False),
    pa.field("tau0", pa.int16(), nullable=False),
    pa.field("x", pa.float32(), nullable=False),
    pa.field("y", pa.float32(), nullable=False),
    pa.field("value", pa.float32(), nullable=True),
])


def calculate_relative_checksum(x_flat, y_flat, v_flat, precision=1e6):
    """
    Calculates a spatial checksum based on relative grid indices.
    
    Parameters:
    -----------
    x_flat, y_flat : np.ndarray (float32)
        Flattened coordinate arrays.
    v_flat : np.ndarray (float32)
        Flattened pixel values.
    precision : float
        Scaling factor for values (default 1e6 for 6 decimal places).
        
    Returns:
    --------
    int : The 64-bit signed integer checksum.
    """
    # 1. Handle NaNs in values early
    # We use a specific constant so it's reproducible in DuckDB (COALESCE)
    v_clean = np.nan_to_num(v_flat, nan=0.0)
    
    # 2. Determine cellsize and origin to calculate relative indices
    # We use round to handle floating point jitter (e.g., 0.999999 -> 1.0)
    x0, y0 = x_flat.min(), y_flat.min()
    
    # Identify cellsize (difference between unique sorted X coordinates)
    # If cellsize is known/constant, you can replace this with a fixed value.
    unique_x = np.unique(x_flat[:1000]) # Sample for speed
    cellsize = np.diff(unique_x).min() if len(unique_x) > 1 else 1.0
    
    # 3. Convert coordinates to integer indices (0, 1, 2...)
    # This keeps the numbers small and avoids HUGETINT overflow in DuckDB
    x_idx = np.round((x_flat - x0) / cellsize).astype(np.int64)
    y_idx = np.round((y_flat - y0) / cellsize).astype(np.int64)
    
    # 4. Scale and round the pixel values
    v_int = np.round(v_clean * precision).astype(np.int64)
    
    # 5. Weighted Sum-Product
    # Weights are prime numbers to ensure uniqueness
    # Result is allowed to overflow/wrap around into negative values (standard in hashing)
    w_x, w_y, w_v = 1003, 1033, 1037
    
    checksum = np.sum(
        (x_idx * w_x) + 
        (y_idx * w_y) + 
        (v_int * w_v), 
        dtype=np.int64
    )
    log.debug(f"Generated Spatial Checksum: {checksum}")
    
    return int(checksum)

def raster_to_parquet_partitioned(
    header,
    field,
    outdir,
    X,
    Y,
    area,
    relTh,
    mu,
    xsi,
    tau0,
    filename="result.parquet",
    ):
    """
    Convert a single raster (2D numpy array) to a flattened Parquet table with columns x, y, value.
    Each raster cell is one row.

    Parameters
    ----------
    header : dict
        Raster header with keys: nrows, ncols, cellsize, xllcenter, yllcenter.
    field : np.ndarray
        2D array of raster values (nrows x ncols)
    outdir : str or Path
        Base directory for results.
    filename : str
        Output Parquet filename
    plot : bool
        Create plot?
    """

    outdir = Path(outdir)
    # --- Parquet partition path (Hive-style) ---
    parquet_partitioned_dir = (
        outdir
        / f"X={X}"
        / f"Y={Y}"
        / f"area={area}"
        / f"relTh={relTh}"
        / f"mu={mu}"
        / f"xsi={xsi}"
        / f"tau0={tau0}"
    )
    parquet_partitioned_dir.mkdir(parents=True, exist_ok=True)

    # Read gridinfo from DEM header
    nrows = header["nrows"]
    ncols = header["ncols"]
    cellsize = header["cellsize"]
    x0 = header["xllcenter"]
    y0 = header["yllcenter"]

    # Compute (grid/pixel cell CENTERS!) coordinates & create grid
    x_coords = x0 + np.arange(ncols) * cellsize
    y_coords = y0 + np.arange(nrows) * cellsize  # SOUTH --> NORTH. AF considers the first line in a data array to be the southernmost one. NO flipping needed! (Bojan 2026-01-12)
    xx, yy = np.meshgrid(x_coords, y_coords)

    # 🔑 Flatten EVERYTHING explicitly
    x_flat = xx.ravel()
    y_flat = yy.ravel()
    v_flat = field.ravel()

    # Calculate Spatial Checksum (use grid index for better speed) with prime number 1003 and 1033 as weights
    spatial_chk = calculate_relative_checksum(x_flat, y_flat, v_flat)

    # Implement & enforce parquet schema ready for data lake
    num_rows = len(v_flat)

    # Build the data dictionary with explicit casting
    # We create full arrays for the partitioning columns so they aren't "dictionaries"
    data = {
        "anriss": pa.array([anriss] * num_rows, type=pa.string()),
        "relTh": pa.array(np.full(num_rows, relTh, dtype=np.float32), type=pa.float32()),
        "mu": pa.array(np.full(num_rows, mu, dtype=np.float32), type=pa.float32()),
        "xsi": pa.array(np.full(num_rows, xsi, dtype=np.int16), type=pa.int16()),
        "tau0": pa.array(np.full(num_rows, tau0, dtype=np.int16), type=pa.int16()),
        "x": pa.array(x_flat, type=pa.float32()),
        "y": pa.array(y_flat, type=pa.float32()),
        "value": pa.array(v_flat, type=pa.float32()),
    }

    # Drop NaNs (Bojan TODO if needed)
    #mask = ~np.isnan(v_flat)  # TODO > threshold?
    #table = pa.table({
    #    "x": x_flat[mask],
    #    "y": y_flat[mask],
    #    "value": v_flat[mask],
    #})

    # Build Arrow table with enforced schema
    table = pa.Table.from_pydict(data, schema=AVAFRAME_SCHEMA)

    # Metadata must be strings
    existing_meta = table.schema.metadata or {}
    custom_meta = {b"spatial_checksum": str(spatial_chk).encode()}
    table = table.replace_schema_metadata({**existing_meta, **custom_meta})

    # write output
    out_file = parquet_partitioned_dir / f"{filename}.parquet"
    pq.write_table(table, out_file, compression="snappy")

    log.debug(f"Parquet table saved to: {out_file}")
