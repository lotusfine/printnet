package com.glaxara.backend.controller;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@CrossOrigin(origins = "${app.cors.origins}")
@RestController
@RequestMapping("/api/novedades")
public class novedadesController {

    @GetMapping
    public List<Map<String, String>> listarNovedades() {
        List<Map<String, String>> novedades = new ArrayList<>();
        
        novedades.add(Map.of(
            "titulo", "¡Llegaron las agendas 2026!", 
            "descripcion", "Vení a buscar la tuya antes de que se agoten."
        ));
        
        novedades.add(Map.of(
            "titulo", "Descuento Estudiantil", 
            "descripcion", "15% off en fotocopias los días martes."
        ));

        return novedades;
    }
}