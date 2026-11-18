import os
import re
import glob
import time
import numpy as np
import pandas as pd

def extract_ym(path):
    m = re.search(r'(\d{4}-\d{2})', os.path.basename(path))
    return m.group(1) if m else None

def main():
    base_dir = os.path.abspath('dataset_apikah')
    hotspot_dir = os.path.join(base_dir, 'hotspot_indonesia')
    iklim_dir = os.path.join(base_dir, 'training_iklim')
    
    output_master_csv = os.path.join(base_dir, 'dataset_utama_apikah.csv')
    output_hotspot_csv = os.path.join(base_dir, 'hotspot_indonesia_2012_2026-09.csv')
    
    h_files = sorted(glob.glob(os.path.join(hotspot_dir, '*.parquet')))
    i_files = sorted(glob.glob(os.path.join(iklim_dir, '*.parquet')))
    
    h_dict = {extract_ym(f): f for f in h_files}
    i_dict = {extract_ym(f): f for f in i_files}
    
    all_months = sorted(set(h_dict.keys()).intersection(set(i_dict.keys())))
    print(f"Total matching months: {len(all_months)} (from {all_months[0]} to {all_months[-1]})")
    
    # Step 1: Build spatial mapping (lat_c, lon_c) -> provinsi
    print("Building cell -> provinsi lookup map from hotspot observations...")
    prov_counts = {}
    for f in h_files:
        df = pd.read_parquet(f, columns=['latitude', 'longitude', 'provinsi'])
        df['lat_c'] = np.round(np.floor(df['latitude'] / 0.25) * 0.25 + 0.125, 3)
        df['lon_c'] = np.round(np.floor(df['longitude'] / 0.25) * 0.25 + 0.125, 3)
        for (lat, lon, prov), cnt in df.groupby(['lat_c', 'lon_c', 'provinsi']).size().items():
            cell = (lat, lon)
            if cell not in prov_counts:
                prov_counts[cell] = {}
            prov_counts[cell][prov] = prov_counts[cell].get(prov, 0) + cnt
            
    cell_prov_map = {cell: max(provs.items(), key=lambda x: x[1])[0] for cell, provs in prov_counts.items()}
    print(f"Lookup map built: {len(cell_prov_map)} grid cells mapped to provinces.")
    
    # Target columns order
    ordered_cols = [
        # Time & Temporal
        'date', 'tahun', 'bulan', 'hari_dalam_tahun', 'acq_time',
        # Spatial & Geography
        'lat_c', 'lon_c', 'latitude', 'longitude', 'provinsi',
        # Hotspot Detection Detail
        'confidence', 'frp', 'bright_ti4', 'daynight', 'satellite', 'produk',
        # Grid Target Metrics
        'ada_api', 'n_hotspot', 'n_hotspot_high', 'max_frp',
        # Meteorology / ERA5
        't2m_mean', 't2m_max', 't2m_min', 'rh_mean', 'rh_min', 'vpd_max', 'wind_max',
        'swvl1_mean', 'precip_mm',
        # Fire Weather Index (FWI) & Drought
        'fwi', 'dc', 'dmc', 'kbdi',
        # Cumulative Precipitation
        'hujan_3h', 'hujan_7h', 'hujan_14h', 'hujan_30h',
        # Anomalies & Climate Teleconnections
        't2m_mean_anom', 'rh_mean_anom', 'precip_mm_anom', 'nino34_lag1', 'dmi_lag1'
    ]
    
    # Step 2: Merge month by month and stream to master CSV
    print(f"\nWriting master dataset to: {output_master_csv}")
    if os.path.exists(output_master_csv):
        os.remove(output_master_csv)
        
    t_start = time.time()
    total_master_rows = 0
    total_hotspots_count = 0
    
    # Open hotspot combined CSV writer as well
    if os.path.exists(output_hotspot_csv):
        os.remove(output_hotspot_csv)
    
    first_chunk_master = True
    first_chunk_hotspot = True
    
    for idx, ym in enumerate(all_months):
        hf = h_dict[ym]
        ikf = i_dict[ym]
        
        # Read hotspot
        h = pd.read_parquet(hf)
        total_hotspots_count += len(h)
        
        # Stream write to combined hotspot CSV
        h.to_csv(output_hotspot_csv, mode='w' if first_chunk_hotspot else 'a', 
                 index=False, header=first_chunk_hotspot)
        first_chunk_hotspot = False
        
        # Read iklim
        i = pd.read_parquet(ikf)
        
        # --- Time Synchronization ---
        h['date'] = h['acq_date'].astype(str)
        i['date'] = pd.to_datetime(i['date']).dt.strftime('%Y-%m-%d')
        
        # --- Spatial Synchronization ---
        h['lat_c'] = np.round(np.floor(h['latitude'] / 0.25) * 0.25 + 0.125, 3)
        h['lon_c'] = np.round(np.floor(h['longitude'] / 0.25) * 0.25 + 0.125, 3)
        i['lat_c'] = np.round(i['lat_c'], 3)
        i['lon_c'] = np.round(i['lon_c'], 3)
        
        # --- Merge ---
        merged = pd.merge(h, i, on=['date', 'lat_c', 'lon_c'], how='outer')
        
        # Time variables alignment
        dt_series = pd.to_datetime(merged['date'])
        merged['tahun'] = dt_series.dt.year.astype('int16')
        merged['bulan'] = dt_series.dt.month.astype('int8')
        merged['hari_dalam_tahun'] = dt_series.dt.dayofyear.astype('int16')
        
        # Target variables alignment for off-grid or non-fire rows
        merged.loc[merged['latitude'].notna() & merged['ada_api'].isna(), 'ada_api'] = 1
        merged.loc[merged['latitude'].notna() & merged['n_hotspot'].isna(), 'n_hotspot'] = 1
        merged.loc[merged['latitude'].notna() & merged['max_frp'].isna(), 'max_frp'] = merged['frp']
        
        # Grid cell default metrics
        merged['ada_api'] = merged['ada_api'].fillna(0).astype('int8')
        merged['n_hotspot'] = merged['n_hotspot'].fillna(0).astype('int32')
        merged['n_hotspot_high'] = merged['n_hotspot_high'].fillna(0).astype('int32')
        
        # Fill missing provinsi using lookup map
        missing_prov = merged['provinsi'].isna()
        if missing_prov.any():
            cells = list(zip(merged.loc[missing_prov, 'lat_c'], merged.loc[missing_prov, 'lon_c']))
            merged.loc[missing_prov, 'provinsi'] = [cell_prov_map.get(c, np.nan) for c in cells]
            
        # Ensure all columns present
        for col in ordered_cols:
            if col not in merged.columns:
                merged[col] = np.nan
                
        # Reorder columns
        merged = merged[ordered_cols]
        
        # Append to master CSV
        merged.to_csv(output_master_csv, mode='w' if first_chunk_master else 'a', 
                      index=False, header=first_chunk_master)
        first_chunk_master = False
        
        total_master_rows += len(merged)
        
        if (idx + 1) % 20 == 0 or (idx + 1) == len(all_months):
            elapsed = time.time() - t_start
            print(f"[{idx+1}/{len(all_months)}] {ym} | Total rows: {total_master_rows:,} | Elapsed: {elapsed:.1f}s")
            
    print(f"\nProcessing complete!")
    print(f"Master CSV rows: {total_master_rows:,}")
    print(f"Master CSV size: {os.path.getsize(output_master_csv) / (1024**3):.2f} GB")
    print(f"Hotspot CSV rows: {total_hotspots_count:,}")
    print(f"Hotspot CSV size: {os.path.getsize(output_hotspot_csv) / (1024**2):.2f} MB")
    print(f"Total time elapsed: {time.time() - t_start:.2f} seconds")

if __name__ == '__main__':
    main()
