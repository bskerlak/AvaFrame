import logging

from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger("com1DFA")

AVAFRAME_SCHEMA = pa.schema([
    pa.field("X_rel_center", pa.float64(), nullable=False),
    pa.field("Y_rel_center", pa.float64(), nullable=False),
    pa.field("area", pa.int16(), nullable=False),
    pa.field("relTh", pa.float32(), nullable=False),
    pa.field("mu", pa.float32(), nullable=False),
    pa.field("xsi", pa.int16(), nullable=False),
    pa.field("tau0", pa.int16(), nullable=False),
    pa.field("x", pa.float32(), nullable=False),
    pa.field("y", pa.float32(), nullable=False),
    pa.field("value", pa.float32(), nullable=True),
])

def calculate_anchored_checksum(x_flat, y_flat, v_flat, x0, y0, precision=1e6, res=5.0):
    """
    Calculates a spatial checksum based on relative grid indices.
    Accepts raw numpy arrays for performance.
    """
    x0 = np.round(float(x0)).astype(np.int64)
    y0 = np.round(float(y0)).astype(np.int64)

    # 1. Calculate indices relative to the fixed anchor (Release Center)
    x_idx = np.round((x_flat - x0) / res).astype(np.int64)
    y_idx = np.round((y_flat - y0) / res).astype(np.int64)
    
    # 2. Scale values to integer space
    v_int = np.round(v_flat * precision).astype(np.int64)
    
    # 3. Standard Weights (Primes)
    w_x, w_y, w_v = 1003, 1033, 1037
    
    # 4. Perform the sum 
    # Using np.sum on raw arrays is faster and avoids Pandas overhead
    checksum = np.sum((x_idx * w_x) + (y_idx * w_y) + (v_int * w_v), 
                      where=(v_int > 0), dtype=np.int64)        

    return int(checksum)

def raster_to_parquet_partitioned(
        header,
        field,
        outdir,
        id_anriss,
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

    # CAUTION: Convert relTh back to [cm]
    relTh = int(float(relTh)*100)

    outdir = Path(outdir)
    # --- Parquet partition path (Hive-style) ---
    parquet_partitioned_dir = (
        outdir
        / f"id_anriss={id_anriss}"
        / f"X_rel_center={X}"
        / f"Y_rel_center={Y}"
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

    # Flatten EVERYTHING explicitly
    x_flat = xx.ravel()
    y_flat = yy.ravel()
    v_flat = field.ravel()

    # Calculate Spatial Checksum (centered on release location)
    spatial_chk = calculate_anchored_checksum(x_flat, y_flat, v_flat, X, Y)

    # Implement & enforce parquet schema ready for data lake
    num_rows = len(v_flat)

    # Build the data dictionary with explicit casting
    # We create full arrays for the partitioning columns so they aren't "dictionaries"
    data = {
        "X_rel_center": pa.array(np.full(num_rows, X, dtype=np.float64), type=pa.float64()),
        "Y_rel_center": pa.array(np.full(num_rows, Y, dtype=np.float64), type=pa.float64()),
        "area": pa.array(np.full(num_rows, area, dtype=np.int16), type=pa.int16()),
        "relTh": pa.array(np.full(num_rows, relTh, dtype=np.float32), type=pa.float32()),
        "mu": pa.array(np.full(num_rows, mu, dtype=np.float32), type=pa.float32()),
        "xsi": pa.array(np.full(num_rows, xsi, dtype=np.int16), type=pa.int16()),
        "tau0": pa.array(np.full(num_rows, tau0, dtype=np.int16), type=pa.int16()),
        "x": pa.array(x_flat, type=pa.float32()),
        "y": pa.array(y_flat, type=pa.float32()),
        "value": pa.array(v_flat, type=pa.float32()),
    }

    if (v_flat.max() == 0) and (v_flat.min() == 0):
        raise ValueError(f"Output field for ASCII file {filename} is zero everywhere")

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
