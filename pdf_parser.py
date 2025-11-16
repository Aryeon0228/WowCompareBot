"""
PDF Parser for WoW Logs
Extracts character names, boss names, and skill data from WoW Logs PDF exports
"""

import PyPDF2
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
    match = re.search(r'^(입힌 피해|치유|받은 피해):\s*(.+?)\s*-\s*(.+?)(?:\s+\(|$)', title)
    if match:
        result['log_type'] = match.group(1)
        result['character'] = match.group(2).strip()
        result['boss'] = match.group(3).strip()

    return result


def parse_table_from_text(lines: List[str], start_idx: int) -> pd.DataFrame:
    """
    Parse table data from text lines
    Assumes table format with columns separated by whitespace
    """
    # Find table header line (usually contains "Name", "Amount", "Casts", etc.)
    header_idx = None
    for i in range(start_idx, min(start_idx + 20, len(lines))):
        line = lines[i]
        if 'Name' in line and ('Amount' in line or 'Casts' in line or 'DPS' in line):
            header_idx = i
            break

    if header_idx is None:
        # Try alternative: look for common WoW log table headers
        for i in range(start_idx, min(start_idx + 20, len(lines))):
            line = lines[i]
            # Check for Korean or common headers
            if any(keyword in line for keyword in ['이름', 'Ability', 'Damage', 'Healing']):
                header_idx = i
                break

    if header_idx is None:
        raise ValueError("Could not find table header in PDF")

    # Parse header to get column names
    header_line = lines[header_idx]
    # Split by multiple spaces (assuming columns are separated by 2+ spaces)
    headers = re.split(r'\s{2,}', header_line.strip())

    # Parse data rows (until we hit an empty line or end of table)
    data_rows = []
    for i in range(header_idx + 1, len(lines)):
        line = lines[i].strip()
        if not line or line.startswith('---') or 'Total' in line and i > header_idx + 10:
            break

        # Split by multiple spaces
        row_data = re.split(r'\s{2,}', line)
        if len(row_data) >= 2:  # Need at least name and one value
            data_rows.append(row_data)

    if not data_rows:
        raise ValueError("No data rows found in table")

    # Create DataFrame
    # Pad rows to match header length
    max_cols = max(len(headers), max(len(row) for row in data_rows))
    headers = headers + [f'Column_{i}' for i in range(len(headers), max_cols)]

    for row in data_rows:
        while len(row) < max_cols:
            row.append('')

    df = pd.DataFrame(data_rows, columns=headers[:max_cols])

    # Clean up column names and data
    df.columns = [col.strip() for col in df.columns]

    # Clean numeric columns (remove commas)
    for col in df.columns:
        if col != 'Name':
            try:
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                df[col] = pd.to_numeric(df[col], errors='ignore')
            except:
                pass

    return df


def parse_pdf(pdf_path: str) -> Dict:
    """
    Parse WoW Logs PDF file and extract data

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
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            if len(pdf_reader.pages) == 0:
                raise ValueError("PDF has no pages")

            # Extract text from first page
            first_page = pdf_reader.pages[0]
            text = first_page.extract_text()

            if not text:
                raise ValueError("Could not extract text from PDF")

            lines = text.split('\n')

            # Find title (usually first non-empty line or contains character name)
            title = None
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if line and ('피해' in line or '-' in line):
                    title = line
                    break

            # Extract metadata from title
            if title:
                metadata = extract_metadata_from_title(title)
                result['character'] = metadata['character']
                result['boss'] = metadata['boss']

            # Find combat duration (format: "1:24" or "84초" or "Combat Time: ...")
            for line in lines[:30]:
                # Look for time format like "1:24" or "84초"
                time_match = re.search(r'(\d+):(\d+)', line)
                if time_match and 'Time' not in line:  # Avoid matching timestamps
                    minutes = int(time_match.group(1))
                    seconds = int(time_match.group(2))
                    if minutes < 60:  # Sanity check (fights rarely > 1 hour)
                        result['combat_duration'] = minutes * 60 + seconds
                        break

                # Look for seconds format
                seconds_match = re.search(r'(\d+)초', line)
                if seconds_match:
                    result['combat_duration'] = int(seconds_match.group(1))
                    break

            # Find total DPS/HPS
            for line in lines[:30]:
                # Look for DPS or HPS numbers (usually formatted with commas)
                dps_match = re.search(r'([\d,]+\.?\d*)\s*DPS', line, re.IGNORECASE)
                if dps_match:
                    dps_str = dps_match.group(1).replace(',', '')
                    try:
                        result['total_dps'] = float(dps_str)
                        break
                    except:
                        pass

                hps_match = re.search(r'([\d,]+\.?\d*)\s*HPS', line, re.IGNORECASE)
                if hps_match:
                    hps_str = hps_match.group(1).replace(',', '')
                    try:
                        result['total_dps'] = float(hps_str)
                        break
                    except:
                        pass

            # Parse table data from text
            df = parse_table_from_text(lines, 0)

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
                'Crit %': 'Crit%',
                'Crit': 'Crit%',
                'Critical': 'Crit%',
                '치명타': 'Crit%',
                'Uptime %': 'Uptime%',
                'Uptime': 'Uptime%',
                '유지 시간': 'Uptime%',
                'DPS': 'DPS',
                'HPS': 'HPS',
                'DTPS': 'DTPS'
            }

            # Rename columns
            df_columns = {col: column_mapping.get(col, col) for col in df.columns}
            df = df.rename(columns=df_columns)

            # Filter out empty rows
            df = df.dropna(how='all')

            # Ensure we have at least Name column
            if 'Name' not in df.columns and len(df.columns) > 0:
                # First column is probably the name
                df = df.rename(columns={df.columns[0]: 'Name'})

            if 'Name' not in df.columns or len(df) == 0:
                raise ValueError("Could not find skill/ability data in PDF table")

            result['dataframe'] = df

    except Exception as e:
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
