"""Exportación a Excel: una hoja por día con el detalle y una hoja de resumen por sede y estado."""
from collections import Counter, defaultdict
from datetime import date, datetime, time
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AZUL = "1F4E79"
FINO = Side(style="thin", color="C9D1DC")
BORDE = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)
CAB_FONT = Font(bold=True, color="FFFFFF")
CAB_FILL = PatternFill("solid", fgColor=AZUL)
COLOR_ESTADO = {
    "PUNTUAL": "DCF5E6", "ASISTIO": "DCF5E6", "PRESENTE": "DCF5E6",
    "TARDANZA": "FFF1D6",
    "FALTA": "FDE4E1", "AUSENTE": "FDE4E1",
    "LICENCIA": "E0ECFB", "VACACIONES": "E0ECFB", "PERMISO": "E0ECFB",
}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

COLUMNAS = [  # (título, ancho)
    ("N°", 5), ("Sede", 16), ("Área ERP", 20), ("Local / tienda", 18), ("Trabajador", 36), ("DNI", 11), ("Estado", 13),
    ("Entrada", 9), ("Salida", 9), ("Horas", 8), ("Motivo / Observaciones", 45),
    ("Autorizado por", 22), ("Origen", 10),
]


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def _horas(a: time | None, b: time | None) -> float | None:
    if not a or not b:
        return None
    seg = (datetime.combine(date.min, b) - datetime.combine(date.min, a)).total_seconds()
    return round(seg / 3600, 2) if seg > 0 else None


def _cabecera(ws, fila: int, titulos: list[str]):
    for c, t in enumerate(titulos, 1):
        cel = ws.cell(fila, c, t)
        cel.font, cel.fill, cel.border = CAB_FONT, CAB_FILL, BORDE
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _titulo(ws, texto: str, sub: str, ancho: int):
    ws.cell(1, 1, texto).font = Font(bold=True, size=14, color=AZUL)
    ws.cell(2, 1, sub).font = Font(italic=True, color="6B7785")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ancho)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ancho)


def _hoja_dia(wb: Workbook, dia: date, filas: list, sede_txt: str, generado: str, sede_de):
    ws = wb.create_sheet(dia.strftime("%d-%m-%Y"))
    _titulo(ws, f"Asistencia del {fecha_larga(dia)}", f"Sede: {sede_txt} · {len(filas)} registros · {generado}",
            len(COLUMNAS))
    _cabecera(ws, 4, [c for c, _ in COLUMNAS])
    for i, (_, ancho) in enumerate(COLUMNAS, 1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    for n, a in enumerate(filas, 1):
        obs = " · ".join(x for x in (a.motivo_ausencia, a.licencia_tipo, a.observaciones) if x)
        valores = [n, sede_de(a), a.area, a.tienda_nombre, a.trabajador_nombre, a.trabajador_dni, a.estado,
                   a.hora_entrada, a.hora_salida, _horas(a.hora_entrada, a.hora_salida), obs,
                   a.autorizado_por, a.origen]
        r = 4 + n
        for c, v in enumerate(valores, 1):
            cel = ws.cell(r, c, v)
            cel.border = BORDE
            cel.alignment = Alignment(vertical="top", wrap_text=c == 11)
        ws.cell(r, 8).number_format = ws.cell(r, 9).number_format = "hh:mm"
        ws.cell(r, 10).number_format = "0.00"
        color = COLOR_ESTADO.get((a.estado or "").upper().split(" ")[0])
        if color:
            ws.cell(r, 7).fill = PatternFill("solid", fgColor=color)

    if not filas:
        ws.cell(5, 1, "Sin registros para este día.").font = Font(italic=True, color="6B7785")
    ws.freeze_panes = "F5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(COLUMNAS))}{4 + max(len(filas), 1)}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "4:4"


def _hoja_resumen(ws, dias: list[date], por_dia: dict, sede_txt: str, generado: str, sede_de):
    estados = sorted({(a.estado or "SIN ESTADO") for fs in por_dia.values() for a in fs})
    titulos = ["Fecha", "Día", "Sede"] + estados + ["Total"]
    _titulo(ws, "Resumen de asistencia", f"Sede: {sede_txt} · del {dias[0]:%d/%m/%Y} al {dias[-1]:%d/%m/%Y} · {generado}",
            len(titulos))
    _cabecera(ws, 4, titulos)
    r = 5
    for d in dias:
        grupos = defaultdict(Counter)
        for a in por_dia.get(d, []):
            grupos[sede_de(a)][a.estado or "SIN ESTADO"] += 1
        for sede, cnt in (sorted(grupos.items()) or [("—", Counter())]):
            valores = [d, DIAS[d.weekday()], sede] + [cnt.get(e, 0) for e in estados] + [sum(cnt.values())]
            for c, v in enumerate(valores, 1):
                cel = ws.cell(r, c, v)
                cel.border = BORDE
            ws.cell(r, 1).number_format = "dd/mm/yyyy"
            ws.cell(r, len(titulos)).font = Font(bold=True)
            r += 1
    # Fila de totales con fórmulas
    ws.cell(r, 3, "TOTAL").font = Font(bold=True)
    for c in range(4, len(titulos) + 1):
        col = get_column_letter(c)
        cel = ws.cell(r, c, f"=SUM({col}5:{col}{r - 1})")
        cel.font, cel.border = Font(bold=True), BORDE
    for c, ancho in enumerate([12, 11, 18] + [12] * (len(estados) + 1), 1):
        ws.column_dimensions[get_column_letter(c)].width = ancho
    ws.freeze_panes = "D5"


def generar(filas: list, desde: date, hasta: date, sede_txt: str, usuario: str, ahora: datetime,
            sedes: dict[str, str] | None = None) -> bytes:
    """filas: asistencias ya filtradas (por sede/estado/búsqueda) entre desde y hasta.
    sedes: {área del ERP en mayúsculas: nombre de la sede en la web}."""
    sedes = sedes or {}
    sede_de = lambda a: sedes.get((a.area or "").upper()) or a.area or "SIN SEDE"
    por_dia: dict[date, list] = defaultdict(list)
    for a in filas:
        por_dia[a.fecha].append(a)
    orden = lambda a: (sede_de(a), a.hora_entrada or time.max, a.trabajador_nombre or "")
    dias = [date.fromordinal(o) for o in range(desde.toordinal(), hasta.toordinal() + 1)]
    generado = f"Generado el {ahora:%d/%m/%Y %H:%M} por {usuario}"

    wb = Workbook()
    _hoja_resumen(wb.active, dias, por_dia, sede_txt, generado, sede_de)
    wb.active.title = "Resumen"
    for d in dias:
        _hoja_dia(wb, d, sorted(por_dia.get(d, []), key=orden), sede_txt, generado, sede_de)
    if len(dias) == 1:
        wb["Resumen"].sheet_view.tabSelected = False  # evita que Excel abra las hojas agrupadas
        wb.active = 1  # un solo día: abrir directamente en el detalle
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
