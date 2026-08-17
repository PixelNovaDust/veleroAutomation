from openpyxl import load_workbook
import os


REQUIRED_COLUMNS = [
    "Namespace",
    "Environment Version",
    "Environment Type",
    "Date",
    "Prod/Non-Prod",
    "Caller",
    "Status",
    "Final Status",
    "Incident ID",
    "Processed",
    "Incident Date",
    "Incident Comment"
]


class ExcelManager:

    def __init__(self, file_path, table_name):
        self.file_path = file_path
        self.table_name = table_name
        self.workbook = None
        self.sheet = None
        self.table = None

    def validate_file(self):

        if not os.path.exists(self.file_path):
        
            raise FileNotFoundError(
                "Excel file not found: {}".format(
                    self.file_path
                )
            )
    
        try:
        
            self.load()
    
            self.validate_columns()
    
        except Exception as error:
        
            raise RuntimeError(
                "Excel validation failed: {}".format(
                    error
                )
            )
    
    def load(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(
                "Excel file not found: {}".format(self.file_path)
            )

        self.workbook = load_workbook(self.file_path)

        for worksheet in self.workbook.worksheets:
            for table in worksheet.tables.values():

                if table.name == self.table_name:
                    self.sheet = worksheet
                    self.table = table
                    return self.sheet

        raise ValueError(
            "Excel table '{}' was not found.".format(
                self.table_name
            )
        )

    def get_headers(self):

        headers = {}

        for cell in self.sheet[1]:
            if cell.value:
                headers[str(cell.value).strip()] = cell.column

        return headers

    def validate_columns(self):

        headers = self.get_headers()

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in headers
        ]

        if missing:
            raise ValueError(
                "Missing required Excel columns: {}".format(
                    ", ".join(missing)
                )
            )

        return headers

    def save(self):
        self.workbook.save(self.file_path)