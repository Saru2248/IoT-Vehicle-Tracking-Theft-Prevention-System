import os
import csv
from datetime import datetime
from fpdf import FPDF

class PDFReport(FPDF):
    def header(self):
        # Brand logo placeholder (colored circle)
        self.set_fill_color(30, 41, 59) # Slate 800
        self.rect(0, 0, 210, 40, 'F')
        
        # Title
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 18)
        self.cell(0, 15, 'IoT Vehicle Tracking & Theft Prevention System', 0, 1, 'C')
        
        # Subtitle
        self.set_font('Helvetica', 'I', 11)
        self.cell(0, 5, 'System Telemetry and Incident History Report', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()} of {{nb}}', 0, 0, 'C')
        self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | IoT Course Project', 0, 0, 'R')

def generate_pdf_report(csv_filepath, pdf_filepath):
    """Parses telemetry CSV and generates a beautiful PDF report.

    Raises RuntimeError with a human-readable message on filesystem or
    data errors so Flask can return a clean 500 JSON response.
    """
    pdf_dir = os.path.dirname(pdf_filepath)
    if pdf_dir:
        try:
            os.makedirs(pdf_dir, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"Cannot create output directory '{pdf_dir}': {exc}") from exc

    # Read telemetry data
    telemetry_data = []
    total_alerts = 0
    max_speed = 0.0
    stolen_events = 0
    geofence_breaches = 0
    immobilized_count = 0
    
    if os.path.exists(csv_filepath):
        with open(csv_filepath, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                telemetry_data.append(row)
                speed = float(row.get("Speed_kmh", 0))
                if speed > max_speed:
                    max_speed = speed
                
                alert = row.get("Alert_Type", "None")
                if alert != "None":
                    total_alerts += 1
                    if "Theft" in alert:
                        stolen_events += 1
                    if "Geofence" in alert:
                        geofence_breaches += 1
                    if "Lock" in alert or "Immobilized" in alert:
                        immobilized_count += 1

    # Initialize FPDF
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Summary Cards Section
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, 'Executive Summary', 0, 1, 'L')
    pdf.line(10, 52, 200, 52)
    pdf.ln(4)
    
    # 2x2 stats block
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(90, 8, f'Total Data Records Logged: {len(telemetry_data)}', 1, 0)
    pdf.cell(10, 8, '', 0, 0) # spacer
    pdf.cell(90, 8, f'Max Recorded Speed: {max_speed:.2f} km/h', 1, 1)
    pdf.ln(2)
    
    pdf.cell(90, 8, f'Security & Theft Alerts: {stolen_events}', 1, 0)
    pdf.cell(10, 8, '', 0, 0) # spacer
    pdf.cell(90, 8, f'Geofence Boundary Breaches: {geofence_breaches}', 1, 1)
    pdf.ln(10)
    
    # Data Table Title
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'Telemetry Log Records', 0, 1, 'L')
    pdf.line(10, 92, 200, 92)
    pdf.ln(4)
    
    # Table Headers
    # Total width = 190 (A4 margins = 10mm left/right)
    col_widths = [38, 22, 22, 18, 45, 45]
    headers = ["Timestamp", "Latitude", "Longitude", "Speed", "Vehicle Status", "Security Alert"]
    
    pdf.set_fill_color(30, 41, 59) # Slate 800
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 8, header, 1, 0, 'C', fill=True)
    pdf.ln()
    
    # Table Rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 8.5)
    
    fill_row = False
    # Show only last 30 entries to keep it clean and fits in A4 page limits, or loop all
    # Let's show the last 20 entries for a concise PDF report
    report_rows = telemetry_data[-22:] if len(telemetry_data) > 22 else telemetry_data
    
    for row in report_rows:
        if fill_row:
            pdf.set_fill_color(241, 245, 249) # Light grey Zebra stripe
        else:
            pdf.set_fill_color(255, 255, 255)
            
        pdf.cell(col_widths[0], 7, row.get("Timestamp", ""), 1, 0, 'C', fill=True)
        pdf.cell(col_widths[1], 7, row.get("Latitude", ""), 1, 0, 'C', fill=True)
        pdf.cell(col_widths[2], 7, row.get("Longitude", ""), 1, 0, 'C', fill=True)
        pdf.cell(col_widths[3], 7, f'{row.get("Speed_kmh", "0")} km/h', 1, 0, 'C', fill=True)
        pdf.cell(col_widths[4], 7, row.get("Status", ""), 1, 0, 'C', fill=True)
        
        # Color code the alert column
        alert_val = row.get("Alert_Type", "None")
        if alert_val != "None" and alert_val != "":
            pdf.set_text_color(220, 38, 38) # Red Alert text
            pdf.set_font('Helvetica', 'B', 8.5)
        else:
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Helvetica', '', 8.5)
            
        pdf.cell(col_widths[5], 7, alert_val, 1, 1, 'C', fill=True)
        fill_row = not fill_row
        
    # Reset formatting
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    
    # Disclaimer / Course Project Notes
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(0, 4, 'Note: This report is generated dynamically by the virtual simulation tracking engine. The GPS logs mimic actual vehicle paths under normal and security threat states. This system fulfills the requirements of IoT Course Project portfolio development.')

    try:
        pdf.output(pdf_filepath)
        print(f"PDF report successfully written to: {pdf_filepath}")
    except (OSError, IOError) as exc:
        raise RuntimeError(f"Cannot write PDF to '{pdf_filepath}': {exc}") from exc
