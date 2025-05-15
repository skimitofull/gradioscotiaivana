import gradio as gr
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import math

# --- CONSTANTES GLOBALES ---
LETTER_WIDTH = 800
LETTER_HEIGHT = 1000
MARGIN = 30
BASE_ROW_HEIGHT = 20
HEADER_HEIGHT = 25
LINE_SPACING = 10
ROWS_PER_PAGE = 25

def split_concept(concept):
    if pd.isnull(concept):
        return ['']
    concept = str(concept).strip()
    parts = []
    if "TRANSF INTERBANCARIA SPEI" in concept:
        parts = [
            'TRANSF INTERBANCARIA SPEI',
            'TRANSF INTERBANCARIA SPEI',
            '/TRANSFERENCIA A'
        ]
        for part in concept.split():
            if part.startswith('202'):
                parts.append(part)
                break
        if "DIC" in concept:
            parts.append("02 DIC")
        elif "NOV" in concept:
            parts.append("19 NOV")
        if "JOSE TOMAS COLSA CHALITA" in concept:
            parts.append("JOSE TOMAS COLSA CHALITA")
        for part in concept.split():
            if part.startswith('//'):
                parts.append(part)
                break
    elif "SCOTIALINE" in concept:
        parts = ["SWEB PAGO A SCOTIALINE"]
        for part in concept.split():
            if part.isdigit() and len(part) > 10:
                parts.append(part)
                break
    else:
        parts = [concept]
    return parts

def clean_amount(amount):
    if pd.isnull(amount) or str(amount).strip() == '':
        return ''
    try:
        if isinstance(amount, str):
            amount = float(amount.replace('$', '').replace(',', ''))
        return '${:,.2f}'.format(amount) if amount != 0 else ''
    except ValueError:
        return ''

def clean_date(date):
    if pd.isnull(date):
        return ''
    try:
        if isinstance(date, str) and ('NOV' in date.upper() or 'DIC' in date.upper()):
            return date.upper().strip()
        return pd.to_datetime(date).strftime('%d %b').upper()
    except:
        return str(date).upper()

def create_page(df, start_idx, end_idx, page_number):
    img = Image.new('RGB', (LETTER_WIDTH, LETTER_HEIGHT), 'white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Helvetica", 9)
        font_bold = ImageFont.truetype("Helvetica-Bold", 10)
    except:
        try:
            font = ImageFont.truetype("Arial", 9)
            font_bold = ImageFont.truetype("Arial Bold", 10)
        except:
            font = ImageFont.load_default()
            font_bold = ImageFont.load_default()
    width = LETTER_WIDTH - (2 * MARGIN)
    headers = ['Fecha', 'Concepto', 'Origen / Referencia', 'Depósito', 'Retiro', 'Saldo']
    col_widths = [
        int(width * 0.08),
        int(width * 0.40),
        int(width * 0.20),
        int(width * 0.11),
        int(width * 0.11),
        int(width * 0.10)
    ]
    col_widths[-1] = width - sum(col_widths[:-1])
    x_positions = np.cumsum([MARGIN] + col_widths[:-1])
    header_color = '#000000'
    header_text_color = '#FFFFFF'
    alternate_row_color = '#F0F0F0'
    border_color = '#E5E5E5'
    y = MARGIN
    for i, header in enumerate(headers):
        x = x_positions[i]
        draw.rectangle([x, y, x + col_widths[i], y + HEADER_HEIGHT],
                      fill=header_color, outline=border_color)
        text_width = draw.textlength(header, font=font_bold)
        text_x = x + (col_widths[i] - text_width) // 2
        draw.text((text_x, y + 5), header, fill=header_text_color, font=font_bold)
    current_y = MARGIN + HEADER_HEIGHT
    for idx in range(start_idx, min(end_idx, len(df))):
        row = df.iloc[idx]
        concept_parts = split_concept(row['Concepto'])
        row_height = max(len(concept_parts) * LINE_SPACING, BASE_ROW_HEIGHT)
        if idx % 2 == 0:
            draw.rectangle([MARGIN, current_y, LETTER_WIDTH - MARGIN, current_y + row_height],
                         fill=alternate_row_color)
        for i, col in enumerate(headers):
            x = x_positions[i]
            value = str(row[col]) if pd.notnull(row[col]) else ''
            if col == 'Concepto':
                for line_idx, line in enumerate(concept_parts):
                    line_y = current_y + (line_idx * LINE_SPACING)
                    draw.text((x + 5, line_y + 2), line, fill='black', font=font)
            elif col in ['Depósito', 'Retiro', 'Saldo']:
                text_width = draw.textlength(value, font=font)
                draw.text((x + col_widths[i] - text_width - 5, current_y + 2),
                         value, fill='black', font=font)
            else:
                draw.text((x + 5, current_y + 2), value, fill='black', font=font)
        draw.line([(MARGIN, current_y + row_height),
                   (LETTER_WIDTH - MARGIN, current_y + row_height)], fill=border_color)
        current_y += row_height
    page_text = f"Página {page_number}"
    text_width = draw.textlength(page_text, font=font)
    draw.text((LETTER_WIDTH - MARGIN - text_width, LETTER_HEIGHT - MARGIN),
              page_text, fill='black', font=font)
    return img

def create_pdf(df):
    total_rows = len(df)
    pages = []
    if total_rows <= ROWS_PER_PAGE:
        pages.append(create_page(df, 0, total_rows, 1))
    else:
        num_pages = math.ceil(total_rows / ROWS_PER_PAGE)
        for page_num in range(num_pages):
            start_idx = page_num * ROWS_PER_PAGE
            end_idx = min((page_num + 1) * ROWS_PER_PAGE, total_rows)
            pages.append(create_page(df, start_idx, end_idx, page_num + 1))
    pdf_buffer = BytesIO()
    if len(pages) == 1:
        pages[0].convert('RGB').save(pdf_buffer, format='PDF')
    else:
        pages[0].convert('RGB').save(pdf_buffer, format='PDF', save_all=True,
                                   append_images=[page.convert('RGB') for page in pages[1:]])
    pdf_buffer.seek(0)
    return pdf_buffer

def generar_estado_cuenta(excel_file):
    try:
        df = pd.read_excel(excel_file)
        df['Fecha'] = df['Fecha'].apply(clean_date)
        df['Depósito'] = df['Depósito'].apply(clean_amount)
        df['Retiro'] = df['Retiro'].apply(clean_amount)
        df['Saldo'] = df['Saldo'].apply(clean_amount)
        pdf_buffer = create_pdf(df)
        return gr.File.update(value=pdf_buffer, visible=True), "¡PDF generado correctamente!"
    except Exception as e:
        return None, f"Error al procesar el archivo: {str(e)}"

with gr.Blocks() as demo:
    gr.Markdown("# Generador de Estado de Cuenta Scotiabank")
    gr.Markdown("Sube tu archivo Excel con movimientos y descarga el PDF generado.")
    excel_input = gr.File(label="Archivo Excel (.xlsx)", file_types=[".xlsx"])
    output_file = gr.File(label="Descargar PDF generado", visible=False)
    status = gr.Textbox(label="Estado", interactive=False)
    btn = gr.Button("Generar PDF")
    btn.click(fn=generar_estado_cuenta, inputs=excel_input, outputs=[output_file, status])

if __name__ == "__main__":
    demo.launch()