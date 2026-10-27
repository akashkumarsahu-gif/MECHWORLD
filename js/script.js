const $ = (selector) => document.querySelector(selector);

const themeToggle = $("#themeToggle");
themeToggle.addEventListener("click", () => {
  document.body.classList.toggle("dark");
  const dark = document.body.classList.contains("dark");
  themeToggle.textContent = dark ? "☀" : "☾";
  themeToggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
});

const menuToggle = $("#menuToggle");
const navLinks = $("#navLinks");
menuToggle.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");
  menuToggle.textContent = open ? "×" : "☰";
  menuToggle.setAttribute("aria-expanded", String(open));
});
navLinks.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
  navLinks.classList.remove("open");
  menuToggle.textContent = "☰";
  menuToggle.setAttribute("aria-expanded", "false");
  navLinks.querySelectorAll("a").forEach((item) => item.classList.remove("active"));
  link.classList.add("active");
}));

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
} else {
  document.querySelectorAll(".reveal").forEach((element) => element.classList.add("visible"));
}

const tools = {
  gear: {
    title: "Gear Ratio Calculator", resultLabel: "OUTPUT SPEED", unit: "RPM",
    fields: [
      { id: "driverTeeth", label: "Driver gear teeth (T₁)", value: 20, min: 1 },
      { id: "drivenTeeth", label: "Driven gear teeth (T₂)", value: 60, min: 1 },
      { id: "inputRPM", label: "Input speed (RPM)", value: 1200, min: 0 }
    ],
    calculate: (v) => {
      const ratio = v.drivenTeeth / v.driverTeeth;
      return { value: v.inputRPM / ratio, unit: "RPM", explanation: `Gear ratio = ${ratio.toFixed(3)}:1. Ideal output speed, ignoring losses.` };
    }
  },
  stress: {
    title: "Normal Stress Calculator", resultLabel: "NORMAL STRESS", unit: "MPa",
    fields: [
      { id: "force", label: "Applied force (N)", value: 10000, min: 0 },
      { id: "area", label: "Cross-sectional area (mm²)", value: 100, min: 0.000001 }
    ],
    calculate: (v) => ({ value: v.force / v.area, unit: "MPa (N/mm²)", explanation: "Normal stress = force ÷ cross-sectional area. Assumes uniform axial loading." })
  },
  power: {
    title: "Mechanical Power Calculator", resultLabel: "MECHANICAL POWER", unit: "kW",
    fields: [
      { id: "torque", label: "Torque (N·m)", value: 50, min: 0 },
      { id: "rpm", label: "Rotational speed (RPM)", value: 1500, min: 0 }
    ],
    calculate: (v) => ({ value: (2 * Math.PI * v.rpm * v.torque) / 60000, unit: "kW", explanation: "Power = 2πNT / 60,000 when N is RPM and torque is N·m." })
  },
  temperature: {
    title: "Temperature Converter", resultLabel: "CONVERTED TEMPERATURE", unit: "°F",
    fields: [
      { id: "temperature", label: "Temperature value", value: 25 },
      { id: "fromUnit", label: "Convert from", type: "select", value: "C", options: [{value:"C",label:"Celsius (°C)"},{value:"F",label:"Fahrenheit (°F)"},{value:"K",label:"Kelvin (K)"}] },
      { id: "toUnit", label: "Convert to", type: "select", value: "F", options: [{value:"C",label:"Celsius (°C)"},{value:"F",label:"Fahrenheit (°F)"},{value:"K",label:"Kelvin (K)"}] }
    ],
    calculate: (v) => {
      const c = v.fromUnit === "C" ? v.temperature : v.fromUnit === "F" ? (v.temperature - 32) * 5/9 : v.temperature - 273.15;
      const result = v.toUnit === "C" ? c : v.toUnit === "F" ? c * 9/5 + 32 : c + 273.15;
      const symbols = {C:"°C",F:"°F",K:"K"};
      return { value: result, unit: symbols[v.toUnit], explanation: `Converted from ${symbols[v.fromUnit]} to ${symbols[v.toUnit]}. Kelvin cannot be below 0 K.` };
    }
  }
};

let currentTool = "gear";
const calcFields = $("#calcFields");
function renderTool(name) {
  currentTool = name;
  const tool = tools[name];
  $("#calcTitle").textContent = tool.title;
  $("#resultLabel").textContent = tool.resultLabel;
  $("#resultUnit").textContent = tool.unit;
  calcFields.innerHTML = tool.fields.map((field) => {
    if (field.type === "select") {
      return `<div class="field"><label for="${field.id}">${field.label}</label><select id="${field.id}">${field.options.map((option) => `<option value="${option.value}" ${option.value === field.value ? "selected" : ""}>${option.label}</option>`).join("")}</select></div>`;
    }
    return `<div class="field"><label for="${field.id}">${field.label}</label><input id="${field.id}" type="number" step="any" value="${field.value}" ${field.min !== undefined ? `min="${field.min}"` : ""} required></div>`;
  }).join("");
  calcFields.querySelectorAll("input, select").forEach((input) => input.addEventListener("input", calculate));
  calculate();
  document.querySelectorAll(".tool-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tool === name));
}
function calculate() {
  const tool = tools[currentTool];
  const values = {};
  for (const field of tool.fields) {
    const input = document.getElementById(field.id);
    const value = field.type === "select" ? input.value : Number(input.value);
    if (field.type !== "select" && (input.value.trim() === "" || !Number.isFinite(value) || (field.min !== undefined && value < field.min))) {
      $("#calcResult").textContent = "Check input";
      $("#resultUnit").textContent = "";
      $("#calcExplanation").textContent = `Enter a valid value for ${field.label.toLowerCase()}.`;
      return;
    }
    values[field.id] = value;
  }
  if (currentTool === "temperature" && values.fromUnit === "K" && values.temperature < 0) {
    $("#calcResult").textContent = "Invalid";
    $("#resultUnit").textContent = "";
    $("#calcExplanation").textContent = "Kelvin cannot be below absolute zero (0 K).";
    return;
  }
  const result = tool.calculate(values);
  if (!Number.isFinite(result.value)) {
    $("#calcResult").textContent = "Invalid";
    $("#resultUnit").textContent = "";
    $("#calcExplanation").textContent = "Please check the input values.";
    return;
  }
  $("#calcResult").textContent = result.value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  $("#resultUnit").textContent = result.unit;
  $("#calcExplanation").textContent = result.explanation;
}
document.querySelectorAll(".tool-tab").forEach((tab) => tab.addEventListener("click", () => renderTool(tab.dataset.tool)));
renderTool("gear");


$("#contactForm").addEventListener("submit", (event) => {
  event.preventDefault();

  const name = $("#contactName").value.trim();
  const email = $("#contactEmail").value.trim();
  const subject = $("#contactSubject").value.trim();
  const message = $("#contactMessage").value.trim();

  const body = `Name: ${name}\nEmail: ${email}\n\n${message}`;

  const recipient = "akashkumarsahuomm4@gmail.com";

  $("#formStatus").textContent =
    "Opening your email app with your message...";

  window.location.href =
    `mailto:${recipient}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
});

$("#year").textContent = new Date().getFullYear();
