"""
Excel and CSV processing service for data extraction and analysis.
"""

import asyncio
import aiofiles
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from pathlib import Path
import csv
import json

import pandas as pd
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException
from ..ai.gemini_service import gemini_service

logger = get_logger(__name__)


class ExcelProcessingError(TelegramAssistantException):
    """Exception for Excel/CSV processing errors."""
    pass


class ExcelProcessor:
    """Service for processing Excel and CSV files."""

    def __init__(self):
        self.supported_formats = ['.xlsx', '.xls', '.csv', '.tsv']
        self.max_size_mb = settings.max_file_size_mb
        self.max_rows = 10000  # Limit for processing large files
        self.max_cols = 100   # Limit for very wide spreadsheets

    def _validate_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate if the file can be processed.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file exists
            if not file_path.exists():
                return False, "File does not exist"

            # Check file extension
            if file_path.suffix.lower() not in self.supported_formats:
                return False, f"Unsupported format. Supported: {', '.join(self.supported_formats)}"

            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_size_mb:
                return False, f"File too large ({file_size_mb:.1f}MB). Max: {self.max_size_mb}MB"

            return True, "Valid file"

        except Exception as e:
            return False, f"Invalid file: {str(e)}"

    async def _read_excel_file(self, file_path: Path) -> Dict[str, pd.DataFrame]:
        """
        Read Excel file and return sheets as DataFrames.

        Args:
            file_path: Path to Excel file

        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        try:
            if file_path.suffix.lower() == '.csv':
                # Handle CSV files
                df = pd.read_csv(file_path, encoding='utf-8')
                return {'Sheet1': df}

            elif file_path.suffix.lower() == '.tsv':
                # Handle TSV files
                df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
                return {'Sheet1': df}

            else:
                # Handle Excel files (.xlsx, .xls)
                sheets_dict = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
                return sheets_dict

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise ExcelProcessingError(f"Could not read file: {e}")

    def _analyze_dataframe(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """
        Analyze a DataFrame to extract metadata and insights.

        Args:
            df: Pandas DataFrame
            sheet_name: Name of the sheet

        Returns:
            Analysis results dictionary
        """
        try:
            # Basic stats
            rows, cols = df.shape

            # Column analysis
            column_info = []
            for col in df.columns:
                col_data = df[col]
                non_null_count = col_data.notna().sum()
                data_type = str(col_data.dtype)

                # Sample values (first few non-null values)
                sample_values = col_data.dropna().head(3).tolist()

                column_info.append({
                    'name': str(col),
                    'data_type': data_type,
                    'non_null_count': int(non_null_count),
                    'null_count': int(rows - non_null_count),
                    'sample_values': [str(v) for v in sample_values]
                })

            # Data type distribution
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            text_cols = df.select_dtypes(include=['object']).columns.tolist()
            date_cols = df.select_dtypes(include=['datetime']).columns.tolist()

            # Summary statistics for numeric columns
            numeric_stats = {}
            if numeric_cols:
                numeric_df = df[numeric_cols]
                for col in numeric_cols:
                    if numeric_df[col].notna().sum() > 0:
                        numeric_stats[col] = {
                            'mean': float(numeric_df[col].mean()) if pd.notna(numeric_df[col].mean()) else None,
                            'min': float(numeric_df[col].min()) if pd.notna(numeric_df[col].min()) else None,
                            'max': float(numeric_df[col].max()) if pd.notna(numeric_df[col].max()) else None,
                            'count': int(numeric_df[col].count())
                        }

            return {
                'sheet_name': sheet_name,
                'dimensions': {'rows': rows, 'columns': cols},
                'columns': column_info,
                'data_types': {
                    'numeric_columns': numeric_cols,
                    'text_columns': text_cols,
                    'date_columns': date_cols
                },
                'numeric_statistics': numeric_stats,
                'memory_usage_mb': df.memory_usage(deep=True).sum() / (1024 * 1024),
                'has_headers': self._likely_has_headers(df),
                'completeness': float(df.notna().sum().sum() / (rows * cols)) if rows * cols > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing DataFrame: {e}")
            return {
                'sheet_name': sheet_name,
                'error': str(e),
                'dimensions': {'rows': 0, 'columns': 0}
            }

    def _likely_has_headers(self, df: pd.DataFrame) -> bool:
        """
        Determine if the DataFrame likely has headers.

        Args:
            df: Pandas DataFrame

        Returns:
            True if likely has headers
        """
        try:
            if len(df) == 0:
                return False

            # Check if first row has different data types than rest
            first_row = df.iloc[0]

            # If all columns in first row are strings and subsequent rows have numbers, likely headers
            first_row_types = [type(v) for v in first_row]
            mostly_strings_first = sum(1 for t in first_row_types if t == str) > len(first_row_types) * 0.7

            if mostly_strings_first and len(df) > 1:
                # Check if subsequent rows have more numeric data
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    return True

            return True  # Default assumption

        except Exception:
            return True

    def _convert_to_text_summary(self, sheets_analysis: Dict[str, Any]) -> str:
        """
        Convert analysis results to text summary for AI processing.

        Args:
            sheets_analysis: Analysis results from all sheets

        Returns:
            Text summary of the spreadsheet
        """
        try:
            summary_parts = []

            for sheet_name, analysis in sheets_analysis.items():
                if 'error' in analysis:
                    summary_parts.append(f"Sheet '{sheet_name}': Error - {analysis['error']}")
                    continue

                dims = analysis['dimensions']
                summary_parts.append(f"\nSheet '{sheet_name}':")
                summary_parts.append(f"- Dimensions: {dims['rows']} rows × {dims['columns']} columns")

                # Column information
                if analysis['columns']:
                    summary_parts.append("- Columns:")
                    for col in analysis['columns'][:10]:  # Limit to first 10 columns
                        sample_text = ', '.join(col['sample_values'][:2]) if col['sample_values'] else 'empty'
                        summary_parts.append(f"  • {col['name']} ({col['data_type']}): {sample_text}")

                # Data types summary
                data_types = analysis['data_types']
                if data_types['numeric_columns']:
                    summary_parts.append(f"- Numeric columns: {', '.join(data_types['numeric_columns'][:5])}")
                if data_types['text_columns']:
                    summary_parts.append(f"- Text columns: {', '.join(data_types['text_columns'][:5])}")

                # Statistics
                if analysis['numeric_statistics']:
                    summary_parts.append("- Key statistics:")
                    for col, stats in list(analysis['numeric_statistics'].items())[:3]:
                        if stats['mean'] is not None:
                            summary_parts.append(f"  • {col}: avg={stats['mean']:.2f}, range={stats['min']:.2f}-{stats['max']:.2f}")

                summary_parts.append(f"- Data completeness: {analysis['completeness']:.1%}")

            return '\n'.join(summary_parts)

        except Exception as e:
            logger.error(f"Error creating text summary: {e}")
            return "Error creating summary"

    async def _generate_ai_insights(self, file_name: str, text_summary: str, sample_data: str) -> Dict[str, Any]:
        """
        Generate AI insights about the spreadsheet data.

        Args:
            file_name: Name of the file
            text_summary: Text summary of structure
            sample_data: Sample data from the spreadsheet

        Returns:
            AI analysis results
        """
        try:
            analysis_prompt = f"""
Analyze this spreadsheet file "{file_name}" based on the structure and sample data:

STRUCTURE SUMMARY:
{text_summary}

SAMPLE DATA:
{sample_data[:2000]}

Please provide analysis as JSON:
{{
    "data_type": "financial/sales/inventory/contacts/etc",
    "key_insights": ["insight1", "insight2", "insight3"],
    "data_quality": "excellent/good/fair/poor",
    "potential_use_cases": ["use1", "use2"],
    "summary": "2-3 sentence summary",
    "contains_sensitive_data": true/false,
    "recommended_actions": ["action1", "action2"]
}}
"""

            ai_response = await gemini_service.generate_response(
                prompt=analysis_prompt,
                temperature=0.3,
                system_instruction="You are a data analysis expert. Analyze spreadsheet data and provide actionable insights."
            )

            # Try to parse JSON response
            try:
                analysis = json.loads(ai_response)
                return analysis
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "data_type": "unknown",
                    "key_insights": ["Analysis completed"],
                    "data_quality": "unknown",
                    "potential_use_cases": ["General data analysis"],
                    "summary": ai_response[:200] + "..." if len(ai_response) > 200 else ai_response,
                    "contains_sensitive_data": False,
                    "recommended_actions": ["Review data structure"]
                }

        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
            return {
                "data_type": "error",
                "key_insights": [],
                "data_quality": "unknown",
                "potential_use_cases": [],
                "summary": f"AI analysis failed: {str(e)}",
                "contains_sensitive_data": False,
                "recommended_actions": []
            }

    def _get_sample_data(self, sheets_dict: Dict[str, pd.DataFrame], max_samples: int = 50) -> str:
        """
        Get sample data from sheets for AI analysis.

        Args:
            sheets_dict: Dictionary of sheet DataFrames
            max_samples: Maximum number of rows to sample

        Returns:
            Formatted sample data string
        """
        try:
            sample_parts = []

            for sheet_name, df in list(sheets_dict.items())[:3]:  # Max 3 sheets
                if len(df) == 0:
                    continue

                sample_size = min(max_samples, len(df))
                sample_df = df.head(sample_size)

                sample_parts.append(f"\n--- Sample from '{sheet_name}' ---")

                # Convert to string representation
                sample_text = sample_df.to_string(max_rows=20, max_cols=10)
                sample_parts.append(sample_text)

            return '\n'.join(sample_parts)

        except Exception as e:
            logger.error(f"Error getting sample data: {e}")
            return "Error extracting sample data"

    async def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process an Excel/CSV file completely.

        Args:
            file_path: Path to file

        Returns:
            Complete processing results
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting Excel/CSV processing for: {file_path.name}")

            # Validate file
            is_valid, validation_message = self._validate_file(file_path)
            if not is_valid:
                raise ExcelProcessingError(validation_message)

            # Read file
            logger.info("Reading spreadsheet data")
            sheets_dict = await self._read_excel_file(file_path)

            # Analyze each sheet
            logger.info(f"Analyzing {len(sheets_dict)} sheet(s)")
            sheets_analysis = {}
            total_rows = 0
            total_cols = 0

            for sheet_name, df in sheets_dict.items():
                analysis = self._analyze_dataframe(df, sheet_name)
                sheets_analysis[sheet_name] = analysis

                if 'dimensions' in analysis:
                    total_rows += analysis['dimensions']['rows']
                    total_cols = max(total_cols, analysis['dimensions']['columns'])

            # Create text summary
            text_summary = self._convert_to_text_summary(sheets_analysis)

            # Get sample data for AI analysis
            sample_data = self._get_sample_data(sheets_dict)

            # Generate AI insights
            logger.info("Generating AI insights")
            ai_insights = await self._generate_ai_insights(file_path.name, text_summary, sample_data)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Compile results
            results = {
                'success': True,
                'file_name': file_path.name,
                'file_size_mb': file_path.stat().st_size / (1024 * 1024),
                'processing_time_seconds': processing_time,
                'file_type': file_path.suffix.lower(),
                'sheet_count': len(sheets_dict),
                'total_rows': total_rows,
                'total_columns': total_cols,
                'sheets_analysis': sheets_analysis,
                'text_summary': text_summary,
                'sample_data': sample_data[:1000],  # Truncated sample
                'ai_insights': ai_insights,
                'processor': 'excel_processor',
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Successfully processed {file_path.name} ({len(sheets_dict)} sheets, {total_rows} rows) in {processing_time:.2f}s")
            return results

        except ExcelProcessingError:
            raise
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Unexpected error processing {file_path.name}: {e}")

            return {
                'success': False,
                'file_name': file_path.name,
                'processing_time_seconds': processing_time,
                'error': str(e),
                'processor': 'excel_processor',
                'timestamp': datetime.now().isoformat()
            }

    async def extract_data_only(self, file_path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """
        Extract only data from file (simplified interface).

        Args:
            file_path: Path to file
            sheet_name: Specific sheet name (None for first sheet)

        Returns:
            Pandas DataFrame
        """
        try:
            # Validate file
            is_valid, validation_message = self._validate_file(file_path)
            if not is_valid:
                raise ExcelProcessingError(validation_message)

            # Read file
            sheets_dict = await self._read_excel_file(file_path)

            if sheet_name and sheet_name in sheets_dict:
                return sheets_dict[sheet_name]
            else:
                # Return first sheet
                return list(sheets_dict.values())[0] if sheets_dict else pd.DataFrame()

        except Exception as e:
            logger.error(f"Error extracting data from {file_path.name}: {e}")
            return pd.DataFrame()

    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if the file format is supported.

        Args:
            file_path: Path to file

        Returns:
            True if format is supported
        """
        return file_path.suffix.lower() in self.supported_formats

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the Excel processing service.

        Returns:
            Health status dictionary
        """
        try:
            # Test pandas/openpyxl functionality
            test_data = {'A': [1, 2, 3], 'B': ['x', 'y', 'z']}
            test_df = pd.DataFrame(test_data)

            # Test basic operations
            test_analysis = self._analyze_dataframe(test_df, 'test')

            return {
                'status': 'healthy',
                'supported_formats': self.supported_formats,
                'max_file_size_mb': self.max_size_mb,
                'max_rows': self.max_rows,
                'max_cols': self.max_cols,
                'pandas_version': pd.__version__,
                'test_analysis_success': 'dimensions' in test_analysis,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Excel processor health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
excel_processor = ExcelProcessor()


async def get_excel_processor() -> ExcelProcessor:
    """Dependency for getting Excel processor."""
    return excel_processor