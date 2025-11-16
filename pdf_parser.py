"""
PDF Parser for WoW Logs
Extracts character names, boss names, and skill data from WoW Logs PDF exports using pdfplumber
"""

import pdfplumber
import pandas as pd
import re
from typing import Dict, Optional, List


def extract_metadata_from_title(title: str) -> Dict[str, Optional[str]]:
    """
    Extract character and boss names from PDF title

    Title format examples:
    - "입힌 피해: Nigromancer - 바위 수호자 Heroic (25 Player)"
    - "치유: CharName - BossName Normal (10 Player)"
    - "받은 피해: CharName - BossName Heroic"

    Returns:
        dict with 'character' and 'boss' keys
    """
    result = {
        'character': None,
        'boss': None,
        'log_type': None
    }

    # Try to match the pattern: {Type}: {Character} - {Boss} ...
    match = re.search(r'^(입힌 피해|치유|받은 피해):\s*(.+?)\s*-\s*(.+?)(?:\s+(?:Heroic|Normal|Mythic|Kill|\()|$)', title)
    if match:
        result['log_type'] = match.group(1)
        result['character'] = match.group(2).strip()
        result['boss'] = match.group(3).strip()

    return result


def clean_table_data(table: List[List]) -> pd.DataFrame:
    """
    Clean and convert table data to DataFrame

    Args:
        table: Raw table data from pdfplumber (list of lists)

    Returns:
        Cleaned pandas DataFrame
    """
    if not table or len(table) < 2:
        raise ValueError("Table has insufficient data")

    # First row is header
    headers = table[0]
    data_rows = table[1:]

    # Remove None values and clean headers
    headers = [str(h).strip() if h is not None else f'Column_{i}' for i, h in enumerate(headers)]

    # Clean data rows - replace None with empty string
    cleaned_rows = []
    for row in data_rows:
        cleaned_row = [str(cell).strip() if cell is not None else '' for cell in row]
        # Skip completely empty rows
        if any(cleaned_row):
            cleaned_rows.append(cleaned_row)

    if not cleaned_rows:
        raise ValueError("No data rows found in table")

    # Ensure all rows have the same number of columns as headers
    max_cols = len(headers)
    for row in cleaned_rows:
        while len(row) < max_cols:
            row.append('')
        # Truncate if too many columns
        if len(row) > max_cols:
            row[:] = row[:max_cols]

    # Create DataFrame
    df = pd.DataFrame(cleaned_rows, columns=headers)

    # Clean numeric columns (remove commas, percentage signs)
    for col in df.columns:
        if col not in ['Name', 'Ability', 'Skill', '이름']:
            try:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                # Try to convert to numeric, but keep as string if fails
                df[col] = pd.to_numeric(df[col], errors='ignore')
            except:
                pass

    return df


def parse_pdf(pdf_path: str) -> Dict:
    """
    Parse WoW Logs PDF file and extract data using pdfplumber

    Returns:
        dict containing:
        - 'dataframe': pandas DataFrame with skill data
        - 'character': character name
        - 'boss': boss name
        - 'combat_duration': combat duration in seconds (if available)
        - 'total_dps': total DPS (if available)
    """
    result = {
        'dataframe': None,
        'character': None,
        'boss': None,
        'combat_duration': None,
        'total_dps': None
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                raise ValueError("PDF has no pages")

            # Extract text from first page for metadata
            first_page = pdf.pages[0]
            text = first_page.extract_text()

            if not text:
                raise ValueError("Could not extract text from PDF")

            lines = text.split('\n')

            print(f"[DEBUG] PDF text lines (first 20):")
            for i, line in enumerate(lines[:20]):
                print(f"  Line {i}: {line[:100]}")

            # Find title (usually first non-empty line or contains character name)
            title = None
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if line and ('피해' in line or '치유' in line or '-' in line):
                    title = line
                    print(f"[DEBUG] Found title: {title}")
                    break

            # Extract metadata from title
            if title:
                metadata = extract_metadata_from_title(title)
                result['character'] = metadata['character']
                result['boss'] = metadata['boss']
                print(f"[DEBUG] Extracted metadata: character={result['character']}, boss={result['boss']}")

            # Find combat duration (format: "1:24" or "84초" or "Combat Time: ...")
            for line in lines[:30]:
                # Look for time format like "1:24" or "84초"
                time_match = re.search(r'(\d+):(\d+)', line)
                if time_match and 'Time' not in line:  # Avoid matching timestamps
                    minutes = int(time_match.group(1))
                    seconds = int(time_match.group(2))
                    if minutes < 60:  # Sanity check (fights rarely > 1 hour)
                        result['combat_duration'] = minutes * 60 + seconds
                        print(f"[DEBUG] Found combat duration: {result['combat_duration']}s")
                        break

                # Look for seconds format
                seconds_match = re.search(r'(\d+)초', line)
                if seconds_match:
                    result['combat_duration'] = int(seconds_match.group(1))
                    print(f"[DEBUG] Found combat duration: {result['combat_duration']}s")
                    break

            # Find total DPS/HPS
            for line in lines[:30]:
                # Look for DPS or HPS numbers (usually formatted with commas)
                dps_match = re.search(r'([\d,]+\.?\d*)\s*DPS', line, re.IGNORECASE)
                if dps_match:
                    dps_str = dps_match.group(1).replace(',', '')
                    try:
                        result['total_dps'] = float(dps_str)
                        print(f"[DEBUG] Found DPS: {result['total_dps']}")
                        break
                    except:
                        pass

                hps_match = re.search(r'([\d,]+\.?\d*)\s*HPS', line, re.IGNORECASE)
                if hps_match:
                    hps_str = hps_match.group(1).replace(',', '')
                    try:
                        result['total_dps'] = float(hps_str)
                        print(f"[DEBUG] Found HPS: {result['total_dps']}")
                        break
                    except:
                        pass

            # Extract tables from PDF
            tables = first_page.extract_tables()

            print(f"[DEBUG] Found {len(tables)} tables in PDF")

            if not tables:
                raise ValueError("No tables found in PDF")

            # Usually the main data table is the largest one
            main_table = max(tables, key=lambda t: len(t) if t else 0)

            print(f"[DEBUG] Main table has {len(main_table)} rows")
            if main_table:
                print(f"[DEBUG] First row (header): {main_table[0]}")
                if len(main_table) > 1:
                    print(f"[DEBUG] Second row (data): {main_table[1]}")

            # Clean and convert to DataFrame
            df = clean_table_data(main_table)

            print(f"[DEBUG] DataFrame shape: {df.shape}")
            print(f"[DEBUG] DataFrame columns: {df.columns.tolist()}")

            # Standardize column names to match CSV format
            column_mapping = {
                'Name': 'Name',
                'Ability': 'Name',
                'Skill': 'Name',
                '이름': 'Name',
                'Amount': 'Amount',
                'Damage': 'Amount',
                'Healing': 'Amount',
                'Total': 'Amount',
                '피해량': 'Amount',
                '치유량': 'Amount',
                'Casts': 'Casts',
                'Uses': 'Casts',
                'Count': 'Casts',
                '시전': 'Casts',
                'Avg Hit': 'Avg',
                'Average': 'Avg',
                'Avg': 'Avg',
                '평균': 'Avg',
                'Crit %': 'Crit %',
                'Crit': 'Crit %',
                'Critical': 'Crit %',
                '치명타': 'Crit %',
                'Uptime %': 'Uptime %',
                'Uptime': 'Uptime %',
                '유지 시간': 'Uptime %',
                'DPS': 'DPS',
                'HPS': 'HPS',
                'DTPS': 'DTPS'
            }

            # Rename columns
            df_columns = {col: column_mapping.get(col, col) for col in df.columns}
            df = df.rename(columns=df_columns)

            # Filter out empty rows
            df = df.dropna(how='all')

            # Filter out rows where Name is empty or invalid
            if 'Name' in df.columns:
                df = df[df['Name'].notna() & (df['Name'] != '') & (df['Name'] != 'None')]

            # Ensure we have at least Name column
            if 'Name' not in df.columns and len(df.columns) > 0:
                # First column is probably the name
                df = df.rename(columns={df.columns[0]: 'Name'})

            if 'Name' not in df.columns or len(df) == 0:
                raise ValueError("Could not find skill/ability data in PDF table")

            result['dataframe'] = df

            print(f"[DEBUG] Final DataFrame shape: {df.shape}")
            print(f"[DEBUG] Final columns: {df.columns.tolist()}")
            if len(df) > 0:
                print(f"[DEBUG] First row: {df.iloc[0].to_dict()}")

    except Exception as e:
        print(f"[ERROR] PDF parsing failed: {str(e)}")
        raise ValueError(f"Failed to parse PDF: {str(e)}")

    return result


def pdf_to_csv_format(pdf_path: str) -> tuple[pd.DataFrame, Dict]:
    """
    Convert PDF to same format as CSV files for compatibility with analyzer

    Returns:
        tuple of (DataFrame, metadata_dict)
    """
    parsed = parse_pdf(pdf_path)

    metadata = {
        'character': parsed['character'],
        'boss': parsed['boss'],
        'combat_duration': parsed['combat_duration'],
        'total_dps': parsed['total_dps']
    }

    return parsed['dataframe'], metadata
