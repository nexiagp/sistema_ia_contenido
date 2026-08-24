"""Domain constants for the blog generation pipeline.
Aligned with the 2026 B2B blog strategy manual.
"""

SEARCH_INTENTS = {
    "informational": {
        "label": "Informacional",
        "description": "El lector quiere entender un problema o concepto. Ej: 'que es X', 'como funciona Y'.",
        "funnel_match": "tofu",
    },
    "comparative": {
        "label": "Comparativa / comercial",
        "description": "El lector evalua opciones. Ej: 'mejor X', 'X vs Y', 'casos de uso'.",
        "funnel_match": "mofu",
    },
    "transactional": {
        "label": "Transaccional",
        "description": "El lector tiene intencion de compra inmediata. Ej: 'precio', 'contratar'.",
        "funnel_match": "bofu",
    },
    "navigational": {
        "label": "Navegacional",
        "description": "Busqueda directa de marca o producto.",
        "funnel_match": "bofu",
    },
}

FUNNEL_STAGES = {
    "tofu": {"label": "TOFU (atraccion)", "description": "Top of funnel: awareness, captacion de trafico organico."},
    "mofu": {"label": "MOFU (consideracion)", "description": "Middle: lead nurturing, comparativas, analisis."},
    "bofu": {"label": "BOFU (decision)", "description": "Bottom: justificacion comercial, ROI, casos cerrados."},
}

FRAMEWORKS = {
    "pas": {
        "label": "PAS (Problema-Agitacion-Solucion)",
        "description": "Estandar B2B en redaccion. Identifica problema, expone consecuencias, presenta solucion.",
    },
    "aida": {
        "label": "AIDA (Atencion-Interes-Deseo-Accion)",
        "description": "Estructura clasica para newsletters y embudos de venta prolongados.",
    },
    "thought_leadership": {
        "label": "Thought Leadership puro",
        "description": "Tesis controvertida o no-obvia respaldada con criterio experto. Estilo SumaCRM.",
    },
    "case_study": {
        "label": "Caso de estudio narrativo",
        "description": "Problema cliente -> intervencion -> resultados verificables.",
    },
}

LEAD_MAGNET_TYPES = {
    "plantilla_operativa": {"label": "Plantilla / automatizacion operativa", "funnel": "tofu"},
    "guia_estrategica": {"label": "Guia estrategica / ebook", "funnel": "mofu"},
    "informe_industria": {"label": "Informe de industria / analitica sectorial", "funnel": "mofu"},
    "auditoria_calculadora": {"label": "Auditoria / calculadora ROI / curso", "funnel": "bofu"},
    "ninguno": {"label": "Sin lead magnet", "funnel": "any"},
}

BLOG_AUDIENCES = {
    "fabricantes": "Fabricantes",
    "distribuidores": "Distribuidores",
    "hoteleros": "Hoteleros y HORECA",
    "industriales": "Suministro industrial",
    "garden": "Garden y agro",
    "actores_proyecto": "Prescriptores y actores de proyecto",
    "mixta": "Mixta",
}

BLOG_CTA_TYPES = {
    "contacto_comercial": "Contacto comercial directo",
    "agendar_llamada": "Agendar llamada / reunion",
    "descarga_lead_magnet": "Descarga de lead magnet",
    "visita_showroom": "Visita al showroom",
    "consulta_servicios": "Consulta de servicios",
    "ninguno": "Sin CTA directa (autoridad)",
}

BLOG_LENGTH_TARGETS = {
    "corto": {"label": "Corto (800-1200 palabras)", "min": 800, "max": 1200},
    "medio": {"label": "Medio (1500-2200 palabras)", "min": 1500, "max": 2200},
    "largo": {"label": "Largo / pillar (2500-3500 palabras)", "min": 2500, "max": 3500},
}

BLOG_STATUSES = ["draft", "review", "ready", "scheduled", "published"]

BLOG_REVIEW_FLAGS = [
    "thin_content_risk",
    "keyword_stuffing_risk",
    "weak_thought_leadership",
    "missing_internal_links",
    "missing_data_or_evidence",
    "off_brand_voice",
    "unsupported_claim_risk",
    "structure_imbalance",
]
