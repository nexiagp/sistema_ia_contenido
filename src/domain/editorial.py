POST_TYPES = {
    "auto": {
        "label": "Auto",
        "pillar": "auto",
        "description": "El planner decide el tipo con mejor encaje.",
    },
    "marca_propuesta_valor": {
        "label": "Marca y propuesta de valor",
        "pillar": "marca_y_propuesta_de_valor",
        "description": "Que hace Nexia, como trabaja y por que su enfoque aporta criterio comercial en Canarias.",
    },
    "educativo_autoridad": {
        "label": "Educativo / autoridad",
        "pillar": "educacion_y_criterio_comercial",
        "description": "Consejos, errores frecuentes, criterios de implantacion y aprendizaje util para el canal B2B.",
    },
    "sector_solucion": {
        "label": "Sector y solucion",
        "pillar": "sectores_y_soluciones",
        "description": "Lectura comercial o tecnica sobre sectores, categorias, soluciones y encaje en canal.",
    },
    "fabricante_colaborador": {
        "label": "Fabricante / colaborador",
        "pillar": "fabricantes_marcas_colaboradores",
        "description": "Visibilidad a marcas o partners sin convertir el post en ficha de catalogo.",
    },
    "proyecto_prescripcion": {
        "label": "Proyecto / prescripcion",
        "pillar": "proyectos_prescripcion_oportunidades",
        "description": "Papel de la prescripcion tecnica, licitaciones, hoteles, residencial, obra y grandes oportunidades.",
    },
    "servicio_proceso_operativa": {
        "label": "Servicio / proceso / operativa",
        "pillar": "servicios_procesos_operativa",
        "description": "Showroom, logistica, stock, reposiciones, formacion, soporte tecnico, pedidos o postventa.",
    },
    "actualidad_lectura_mercado": {
        "label": "Actualidad / lectura de mercado",
        "pillar": "actualidad_y_lectura_de_mercado",
        "description": "Convertir una novedad o movimiento en interpretacion util para fabricantes y distribuidores.",
    },
}

CHANNELS = {
    "linkedin": "LinkedIn",
    "x": "X",
    "facebook": "Facebook",
}

AUDIENCES = {
    "fabricantes": "Fabricantes",
    "distribuidores": "Distribuidores",
    "actores_proyecto": "Actores de proyecto",
    "mixta": "Mixta",
}

OBJECTIVES = {
    "autoridad": "Autoridad",
    "confianza": "Confianza",
    "visibilidad_ecosistema": "Visibilidad de ecosistema",
    "conversion_suave": "Conversion suave",
    "actualidad": "Actualidad",
    "educacion": "Educacion",
}

CTA_TYPES = {
    "contacto": "Contacto",
    "comentario": "Comentario",
    "visita_showroom": "Visita showroom",
    "mas_info": "Mas informacion",
    "sin_cta_directa": "Sin CTA directa",
}

RISK_FLAGS = [
    "unsupported_claim_risk",
    "brand_overpromotion_risk",
    "too_generic_risk",
    "too_corporate_risk",
    "too_many_ideas_risk",
    "news_dependency_risk",
]

MASTER_POST_TYPES = [key for key in POST_TYPES.keys() if key != "auto"]
