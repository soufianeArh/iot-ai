package com.soufiane.device.controller;

import com.soufiane.device.dto.DeviceCreateRequest;
import com.soufiane.device.dto.DeviceResponse;
import com.soufiane.device.dto.DeviceUpdateRequest;
import com.soufiane.device.dto.UnregisteredSighting;
import com.soufiane.device.service.DeviceIngestService;
import com.soufiane.device.service.DeviceService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.List;

//controller: bean + endpt regitery
//response body skips: html rendering to JSON body
@RestController
@RequestMapping("/api/devices")
//CRUD on devides
public class DeviceController {

    private final DeviceService deviceService;
    private final DeviceIngestService deviceIngestService;

    public DeviceController(DeviceService deviceService, DeviceIngestService deviceIngestService) {
        this.deviceService = deviceService;
        this.deviceIngestService = deviceIngestService;
    }

    @GetMapping
    public List<DeviceResponse> list() {
        return deviceService.findAll();
    }


    // targets the IngesService for unregisterd to get them ONLY
    //POST is mqqt subscriber job
    //list them  until it's evicted (200-cap pushes it out) or the service restarts
    //no route yet to delete an unregistered device!!!
    @GetMapping("/unregistered")
    public List<UnregisteredSighting> unregistered() {
        return deviceIngestService.listUnregistered();
    }

    @GetMapping("/{id}")
    public DeviceResponse get(@PathVariable Long id) {
        return deviceService.findById(id);
    }

    @PostMapping
    public ResponseEntity<DeviceResponse> create(@Valid @RequestBody DeviceCreateRequest request,
                                                 UriComponentsBuilder uriBuilder) {
        DeviceResponse created = deviceService.create(request);
        return ResponseEntity
                .created(uriBuilder.path("/api/devices/{id}").build(created.id()))
                .body(created);
    }

    @PutMapping("/{id}")
    public DeviceResponse update(@PathVariable Long id, @Valid @RequestBody DeviceUpdateRequest request) {
        return deviceService.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        deviceService.delete(id);
    }
}
