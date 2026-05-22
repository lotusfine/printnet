package com.glaxara.backend.controller;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/novedades")
public class novedadesController {

    @GetMapping
    public List<Map<String, String>> listarNovedades() {
        List<Map<String, String>> novedades = new ArrayList<>();
        

        return novedades;
    }
}