package com.example.demo.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller
@RequestMapping(value = "/demo")
public class DemoController {
	@ResponseBody
	@RequestMapping(value = "/version", method = RequestMethod.GET, produces = "application/json;charset=UTF-8")
	public String version() {
		return "{\"version\":\"1.0.0\",\"message\":\"hello world\"}";
	}

}
