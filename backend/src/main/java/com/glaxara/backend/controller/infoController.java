package com.glaxara.backend.controller;

import java.util.HashMap;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;


@RestController
@RequestMapping("/api")

public class infoController {

    @GetMapping("informacion")
    public Map<String, String> getInfo(){
        Map<String, String> info = new HashMap<>();

        info.put("horarios", "Lunes a Viernes de 7:30 a 13:30 hs y de 16:30 a 19:30 hs. Sábados de 10:00 a 13:00 hs. Domingos cerrado.");
        info.put("direccion", "https://maps.app.goo.gl/aUt7ptFJBFfZBqVv7");

        return info;
    }
}
    
