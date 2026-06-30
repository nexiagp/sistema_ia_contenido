"""
Script de descarga centralizada de la KB externa para Nexia GP.
Guarda todos los PDFs en data/uploads/kb-externa/ organizados por bloque.
Uso: python scripts/download_kb.py
"""
import os
import sys
import ssl
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "uploads" / "kb-externa"
DEST.mkdir(parents=True, exist_ok=True)

# Crear subdirectorios por bloque
BLOCKS = ["A-economia", "B-fiscal", "C-turismo", "D-logistica", "E-industria", "F-demografia", "G-digital", "Z-garden"]
for b in BLOCKS:
    (DEST / b).mkdir(exist_ok=True)

DOCS = [
    # ====== A) ECONOMÍA Y DATOS MACRO ======
    {
        "block": "A-economia",
        "name": "A01_Informe-Economico-Presupuestos-Canarias-2026.pdf",
        "url": "https://www.gobiernodecanarias.org/cmsgob2/export/sites/economia/galeria/Galeria_politica_economica_2/Informe-Economico-PGCAC-2026def.pdf",
        "score": 10,
    },
    {
        "block": "A-economia",
        "name": "A02_CES-Canarias-Informe-Anual-2024.pdf",
        "url": "https://datosdelanzarote.lztic.com/media/item/docs/Afdg-Informe-Anual-CES-2024.pdf",
        "score": 9,
    },
    {
        "block": "A-economia",
        "name": "A03_BBVA-Research-Situacion-Canarias-2026.pdf",
        "url": "https://www.bbvaresearch.com/wp-content/uploads/2026/04/Situacion_Canarias_abril_26.pdf",
        "score": 9,
    },
    {
        "block": "A-economia",
        "name": "A04_BBVA-Research-Situacion-Canarias-2025.pdf",
        "url": "https://www.bbvaresearch.com/wp-content/uploads/2025/05/Situacion-Canarias-2025.pdf",
        "score": 9,
    },
    {
        "block": "A-economia",
        "name": "A05_CCE-Economia-Internacional-Cap14-2024.pdf",
        "url": "https://ccelpa.org/informe-anual/IA2024/pdf/indicadores/14-2024.pdf",
        "score": 9,
    },
    {
        "block": "A-economia",
        "name": "A06_Presupuestos-Canarias-2026-Tomo4-Informe-Economico.pdf",
        "url": "https://www.gobiernodecanarias.org/cmsgob1/export/sites/hacienda/planificacionypresupuesto/galeria/Presupuestos/2026/ley/TOMO-4-Informe-Economico-y-Financiero-y-Memorias-explicativas.pdf",
        "score": 9,
    },
    {
        "block": "A-economia",
        "name": "A07_CEOE-Tenerife-Coyuntura-4T-2025.pdf",
        "url": "https://ceoe-tenerife.com/wp-content/uploads/T019-25.4-INFORME-DE-COYUNTURA-ECONOMICA-DE-CANARIAS-4T25.pdf",
        "score": 8,
    },
    {
        "block": "A-economia",
        "name": "A08_Observatorio-Vivienda-Suelo-Boletin-Anual-2024.pdf",
        "url": "https://www.lamoncloa.gob.es/serviciosdeprensa/notasprensa/vivienda-agenda-urbana/Documents/2025/040725-ObservatoriodeviviendaysueloBoletnanual24.pdf",
        "score": 7,
    },
    # ====== B) REF / ZEC / RIC ======
    {
        "block": "B-fiscal",
        "name": "B01_AEAT-Manual-Practico-Sociedades-2024.pdf",
        "url": "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/Sociedades/Manual_Sociedades_2024.pdf",
        "score": 10,
    },
    {
        "block": "B-fiscal",
        "name": "B02_Parlamento-Canarias-Dictamen-Revision-REF-2025.pdf",
        "url": "https://www.parcan.es/files/pub/bop/11l/2025/413/bo413.pdf",
        "score": 10,
    },
    {
        "block": "B-fiscal",
        "name": "B03_Guia-Fiscal-Gran-Canaria-2024-PwC-SPEGC.pdf",
        "url": "https://bestingrancanaria.com/wp-content/uploads/2024/09/guiafiscal_ESP_2024_VFINAL.pdf",
        "score": 9,
    },
    {
        "block": "B-fiscal",
        "name": "B04_ZEC-Informe-Gestion-2023.pdf",
        "url": "https://canariaszec.com/wp-content/uploads/2025/03/BASE_memoria_Anual_2023_FINAL_v3.pdf",
        "score": 9,
    },
    {
        "block": "B-fiscal",
        "name": "B05_BIPLAZA-Guia-Constituir-Empresas-ZEC.pdf",
        "url": "https://one.gob.es/sites/default/files/2025-01/Gu%C3%ADa%20para%20constituir%20empresas%20en%20la%20zona%20ZEC%20de%20Canarias%20-%20BIPLAZA.pdf",
        "score": 9,
    },
    {
        "block": "B-fiscal",
        "name": "B06_Cronica-RIC-2024-Miranda-Calderin-Hacienda-Canaria.pdf",
        "url": "https://www3.gobiernodecanarias.org/tributos/atc/documents/65729/32197933/63.3.pdf/1e615474-89ed-a9bb-73e7-698b5cee1c16?t=1746616656445",
        "score": 9,
    },
    # ====== C) TURISMO Y HOSTELERÍA ======
    {
        "block": "C-turismo",
        "name": "C01_EXCELTUR-IMPACTUR-Canarias-2024-Avance-2025.pdf",
        "url": "https://www.exceltur.org/wp-content/uploads/2026/05/Estudio-IMPACTUR-Canarias-2024-y-Avance-2025_.pdf",
        "score": 9,
    },
    {
        "block": "C-turismo",
        "name": "C02_EXCELTUR-Perspectivas-N95-Balance-2025-Previsiones-2026.pdf",
        "url": "https://www.exceltur.org/wp-content/uploads/2026/01/EXCELTUR-Informe-Perspectivas-N95-Balance-del-ano-2025-y-previsiones-para-2026.pdf",
        "score": 9,
    },
    {
        "block": "C-turismo",
        "name": "C03_Balance-Situacion-Turistica-Tenerife-2025.pdf",
        "url": "https://www.webtenerife.com/-/media/files/investigacion/situacion-turistica/informes-de-situacin-turstica-de-tenerife/relateddocuments/2025/balance-de-situacin-turstica-de-tenerife-2025.pdf",
        "score": 9,
    },
    {
        "block": "C-turismo",
        "name": "C04_CCE-Sector-Turistico-Cap08-2024.pdf",
        "url": "https://www.ccelpa.org/informe-anual/IA2024/pdf/indicadores/08-2024.pdf",
        "score": 8,
    },
    {
        "block": "C-turismo",
        "name": "C05_Sostenibilidad-Turismo-Canarias-2024-ULL.pdf",
        "url": "https://riull.ull.es/xmlui/bitstream/handle/915/43153/Sostenibilidad-del-Turismo-de-Canarias-Informe-anual-2024.pdf?sequence=1&isAllowed=y",
        "score": 8,
    },
    # ====== D) LOGÍSTICA Y PUERTOS ======
    {
        "block": "D-logistica",
        "name": "D01_AP-Tenerife-Memoria-Anual-2024.pdf",
        "url": "https://www.puertos.es/sites/default/files/2026-03/Memoria%20Anual%202024%20AP%20Santa%20Cruz%20de%20Tenerife.pdf",
        "score": 9,
    },
    {
        "block": "D-logistica",
        "name": "D02_AP-Tenerife-Memoria-Sostenibilidad-2023-PlanEmpresa-2025.pdf",
        "url": "https://www.puertosdetenerife.org/wp-content/uploads/2025/01/MEMORIA-DE-SOSTENIBILIDAD-2023-PlanEmpresa-2025.-Definitiva.pdf",
        "score": 9,
    },
    {
        "block": "D-logistica",
        "name": "D03_OPPE-Anuario-Estadistico-Portuario-2024.pdf",
        "url": "https://www.puertos.es/sites/default/files/2025-10/Anuario%20Estad%C3%ADstico%20OPPE%202024.pdf",
        "score": 8,
    },
    # D04 OTLE requiere descarga manual (403 para bots) — se omite, nota al final
    # ====== E) CONSTRUCCIÓN / INDUSTRIA / HORECA ======
    {
        "block": "E-industria",
        "name": "E01_EDIC-Estrategia-Desarrollo-Industrial-Canarias-2022-2027.pdf",
        "url": "https://oic.itccanarias.org/wp-content/uploads/2022/03/EDIC-22.27-15-de-marzo.pdf",
        "score": 9,
    },
    {
        "block": "E-industria",
        "name": "E02_CCE-Construccion-Cap06-2024.pdf",
        "url": "https://www.ccelpa.org/informe-anual/IA2024/pdf/indicadores/06-2024.pdf",
        "score": 8,
    },
    {
        "block": "E-industria",
        "name": "E03_CCE-Mapa-Vacantes-Empleo-Necesidades-Formacion.pdf",
        "url": "https://ccelpa.org/wp-content/uploads/2026/01/02-A4-Informe-CCE-Mapas-de-vacantes-de-empleo.pdf",
        "score": 8,
    },
    {
        "block": "E-industria",
        "name": "E04_CCOO-Hosteleria-Turismo-Espana-2025.pdf",
        "url": "https://www.ccoo-servicios.es/archivos/20250121_Informe_host-Y-turismo.pdf",
        "score": 7,
    },
    # ====== F) DEMOGRAFÍA EMPRESARIAL ======
    {
        "block": "F-demografia",
        "name": "F01_FAEDPYME-Informe-PYME-Canarias-2025.pdf",
        "url": "https://oepyme.ulpgc.es/wp-content/uploads/FAEDPYME_2025.pdf",
        "score": 9,
    },
    {
        "block": "F-demografia",
        "name": "F02_FAEDPYME-Informe-PYME-Canarias-2024-Talento.pdf",
        "url": "https://oepyme.ulpgc.es/wp-content/uploads/Informe-PYME-CANARIAS-2024.pdf",
        "score": 9,
    },
    {
        "block": "F-demografia",
        "name": "F03_CCE-Estructura-Empresarial-Cap00-2024.pdf",
        "url": "https://www.ccelpa.org/informe-anual/IA2024/pdf/indicadores/00-2024.pdf",
        "score": 9,
    },
    {
        "block": "F-demografia",
        "name": "F04_DGIPYME-Estructura-Dinamica-Empresarial-Espana-2023.pdf",
        "url": "https://industria.gob.es/es-es/estadisticas/Estadisticas_Territoriales/Estructura-Dinamica-Empresarial-2023.pdf",
        "score": 9,
    },
    # ====== G) DIGITALIZACIÓN Y COMPETITIVIDAD ======
    {
        "block": "G-digital",
        "name": "G01_OCTSI-eCanarias-2024-Sociedad-Digital.pdf",
        "url": "https://www.octsi.es/images/documentos/2025/informe_ecanarias_2024.pdf",
        "score": 9,
    },
    {
        "block": "G-digital",
        "name": "G02_ONTSI-Digitalizacion-PYMEs-2024-Analisis-Comparado.pdf",
        "url": "https://www.ontsi.es/sites/ontsi/files/2024-12/informedigitalizacionpymes-analisiscomparado2024.pdf",
        "score": 9,
    },
    {
        "block": "G-digital",
        "name": "G03_FBBVA-Ivie-Productividad-Competitividad-Espana-OPCE-2025.pdf",
        "url": "https://www.fbbva.es/wp-content/uploads/2026/01/OPCE_Informe_2025_version_preliminar.pdf",
        "score": 9,
    },
    # ====== Z) GARDEN / SECTOR VERDE ======
    {
        "block": "Z-garden",
        "name": "Z01_MAPA-Cifras-Flor-Cortada-Planta-Ornamental-2023.pdf",
        "url": "https://www.mapa.gob.es/dam/mapa/contenido/agricultura/temas/producciones-agricolas/frutas-y-hortalizas/flores-y-plantas-ornamentales/cifrasdelsectordeflorcortadayplanta2023junio2024.pdf",
        "score": 5,
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}

ctx = ssl.create_default_context()
# Algunos servidores gubernamentales tienen certs raros
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def download(doc: dict) -> dict:
    dest_path = DEST / doc["block"] / doc["name"]
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        size_mb = dest_path.stat().st_size / 1_048_576
        return {"status": "SKIP", "name": doc["name"], "size_mb": round(size_mb, 2)}

    try:
        req = urllib.request.Request(doc["url"], headers=HEADERS)
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.ProxyHandler({})
        )
        with opener.open(req, timeout=120) as resp:
            data = resp.read()

        if len(data) < 500:
            return {"status": "ERROR", "name": doc["name"], "error": f"Respuesta demasiado pequeña: {len(data)} bytes"}

        dest_path.write_bytes(data)
        size_mb = len(data) / 1_048_576
        return {"status": "OK", "name": doc["name"], "size_mb": round(size_mb, 2)}

    except Exception as e:
        return {"status": "ERROR", "name": doc["name"], "error": str(e)[:120]}


def main():
    total = len(DOCS)
    ok = skip = err = 0
    total_mb = 0.0

    print(f"\n{'='*65}")
    print(f"  NEXIA GP — Descarga KB Externa ({total} documentos)")
    print(f"  Destino: {DEST}")
    print(f"{'='*65}\n")

    for i, doc in enumerate(DOCS, 1):
        print(f"[{i:02d}/{total}] {doc['name'][:55]:<55}", end=" ", flush=True)
        r = download(doc)
        if r["status"] == "OK":
            print(f"OK  {r['size_mb']:.1f} MB")
            ok += 1
            total_mb += r["size_mb"]
        elif r["status"] == "SKIP":
            print(f"->  ya existe ({r['size_mb']:.1f} MB)")
            skip += 1
            total_mb += r["size_mb"]
        else:
            print(f"!!  {r['error']}")
            err += 1
        time.sleep(0.8)  # respetuoso con los servidores

    print(f"\n{'='*65}")
    print(f"  RESULTADO: {ok} descargados | {skip} ya existían | {err} fallidos")
    print(f"  Total en disco: ~{total_mb:.0f} MB")
    print(f"{'='*65}")
    print(f"\nNOTA: El informe OTLE 2024 requiere descarga manual (403 para bots):")
    print(f"  https://otle.transportes.gob.es/informes-anuales-monograficos/informes-anuales/informe-anual-otle-2024")
    print(f"\nLa carpeta de destino: {DEST}")
    print("Puedes importarla desde la sección Library > Importar local de la app.\n")


if __name__ == "__main__":
    main()
