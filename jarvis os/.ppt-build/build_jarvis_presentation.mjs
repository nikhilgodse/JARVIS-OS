import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/ASUS/OneDrive/Attachments/Desktop/jarvis os";
const SKILL_DIR = "C:/Users/ASUS/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const TMP_DIR = path.join(workspaceDir, ".ppt-build");
const FINAL_PPTX = path.join(workspaceDir, "output", "JARVIS_OS_Project_Presentation_v2.pptx");
const RUNTIME_PYTHON = "C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const { resolvePresentationFont, makeNativeBulletParagraphs, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")).href,
);

await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const font = resolvePresentationFont();
const W = 1280, H = 720;
const C = {
  bg: "#06111F", panel: "#0A1B2E", panel2: "#0C2239", cyan: "#2BD9FF",
  cyan2: "#8CEBFF", blue: "#2D7CFF", purple: "#8B6CFF", lime: "#6FE7B6",
  amber: "#F4C66A", red: "#FF8191", white: "#F3FAFF", text: "#C9DAE8",
  muted: "#88A2B8", line: "#1C4664", dark: "#04101C"
};

const presentation = Presentation.create({ slideSize: { width: W, height: H } });
presentation.theme.colorScheme = {
  name: "Jarvis Tech", themeColors: {
    accent1: C.cyan, accent2: C.blue, accent3: C.purple, accent4: C.lime,
    accent5: C.amber, accent6: C.red, bg1: C.bg, bg2: C.panel,
    tx1: C.white, tx2: C.text, dk1: "#000000", dk2: C.dark,
    lt1: "#FFFFFF", lt2: "#DCECF5", hlink: C.cyan, folHlink: C.purple,
  }
};

function shape(slide, geometry, left, top, width, height, fill = "none", line = { style: "solid", fill: C.line, width: 1 }, radius) {
  return slide.shapes.add({ geometry, position: { left, top, width, height }, fill, line, borderRadius: radius });
}
function text(slide, value, left, top, width, height, opts = {}) {
  const s = shape(slide, "textbox", left, top, width, height, "none", { style: "solid", fill: "none", width: 0 });
  s.text = value;
  s.text.style = {
    typeface: font, fontSize: opts.size ?? 22, bold: opts.bold ?? false,
    color: opts.color ?? C.text, alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top", autoFit: "shrinkText",
    lineSpacing: opts.lineSpacing ?? 1.05,
    insets: opts.insets ?? { top: 2, right: 3, bottom: 2, left: 3 },
  };
  return s;
}
function box(slide, label, left, top, width, height, opts = {}) {
  const s = shape(slide, opts.geometry ?? "roundRect", left, top, width, height,
    opts.fill ?? C.panel, opts.line ?? { style: "solid", fill: opts.lineColor ?? C.line, width: opts.lineWidth ?? 1 }, opts.radius ?? 14);
  if (label !== undefined && label !== "") {
    s.text = label;
    s.text.style = {
      typeface: font, fontSize: opts.size ?? 20, bold: opts.bold ?? true,
      color: opts.color ?? C.white, alignment: opts.align ?? "center",
      verticalAlignment: opts.valign ?? "middle", autoFit: "shrinkText",
      lineSpacing: 1.0, insets: opts.insets ?? { top: 5, right: 8, bottom: 5, left: 8 },
    };
  }
  return s;
}
function connect(slide, a, b, from = "bottom", to = "top", color = C.cyan, kind = "straight") {
  return slide.shapes.connect(a, b, { kind, fromSide: from, toSide: to,
    line: { style: "solid", fill: color, width: 2 }, tail: { type: "triangle", width: "sm", length: "sm" } });
}
function base(slide, n, title, section = "") {
  slide.background.fill = C.bg;
  shape(slide, "rect", 0, 0, W, 8, C.cyan, { style: "solid", fill: C.cyan, width: 0 });
  if (section) text(slide, section.toUpperCase(), 58, 28, 360, 20, { size: 13, bold: true, color: C.cyan });
  text(slide, title, 58, 50, 1100, 54, { size: 40, bold: true, color: C.white });
  shape(slide, "line", 58, 113, 1164, 0, "none", { style: "solid", fill: C.line, width: 1 });
  shape(slide, "line", 58, 677, 1164, 0, "none", { style: "solid", fill: C.line, width: 1 });
  text(slide, "JARVIS OS – Intelligent Voice-Controlled Desktop Assistant", 58, 686, 800, 18, { size: 12, color: C.muted });
  text(slide, String(n).padStart(2, "0"), 1172, 684, 50, 20, { size: 13, color: C.cyan, align: "right", bold: true });
}
function note(slide, value) {
  slide.speakerNotes.textFrame.setText(value);
}
function bullets(slide, items, left, top, width, height, opts = {}) {
  const s = shape(slide, "textbox", left, top, width, height, "none", { style: "solid", fill: "none", width: 0 });
  s.text = makeNativeBulletParagraphs(items, { marginLeftPoints: 18, hangingPoints: 9, spaceAfterPoints: opts.spaceAfter ?? 7 });
  s.text.style = { typeface: font, fontSize: opts.size ?? 21, color: opts.color ?? C.text, autoFit: "shrinkText", lineSpacing: opts.lineSpacing ?? 1.08, insets: { top: 3, right: 3, bottom: 3, left: 3 } };
  return s;
}
function chip(slide, label, left, top, width, color = C.cyan) {
  return box(slide, label, left, top, width, 26, { fill: "#0A2940", lineColor: color, size: 12, color, radius: 13 });
}
function verticalFlow(slide, labels, left, top, width, gap = 11, height = 43, colors = []) {
  const arr = [];
  labels.forEach((label, i) => {
    const b = box(slide, label, left, top + i * (height + gap), width, height, { fill: C.panel, lineColor: colors[i] ?? C.line, size: 17, color: C.white });
    arr.push(b);
    if (i) connect(slide, arr[i - 1], b, "bottom", "top", colors[i] ?? C.cyan);
  });
  return arr;
}
function statusLabel(slide, label, left, top, color) {
  return box(slide, label, left, top, 170, 27, { fill: "#0A2940", lineColor: color, color, size: 12, radius: 13 });
}

// 1. Title
{
  const s = presentation.slides.add();
  s.background.fill = C.bg;
  shape(s, "rect", 0, 0, W, 8, C.cyan, { style: "solid", fill: C.cyan, width: 0 });
  text(s, "BE COMPUTER ENGINEERING  |  PROJECT PRESENTATION", 68, 56, 680, 22, { size: 14, bold: true, color: C.cyan });
  text(s, "JARVIS OS", 68, 124, 620, 72, { size: 62, bold: true, color: C.white });
  text(s, "Intelligent Voice-Controlled\nDesktop Assistant", 70, 210, 610, 88, { size: 32, color: C.cyan2, lineSpacing: 0.95 });
  text(s, "An AI-powered desktop automation system that turns natural-language commands into computer actions.", 70, 326, 560, 58, { size: 22, color: C.text, lineSpacing: 1.05 });
  const info = box(s, "", 70, 470, 555, 135, { fill: C.panel, lineColor: C.line, radius: 14 });
  text(s, "Student: [Name]    |    Guide: [Name]", 92, 492, 500, 27, { size: 18, color: C.white });
  text(s, "Department / College: [Name]", 92, 530, 500, 25, { size: 18, color: C.text });
  text(s, "Academic Year: [Year]", 92, 565, 500, 24, { size: 18, color: C.text });
  const user = box(s, "USER", 880, 132, 205, 54, { fill: C.panel2, lineColor: C.cyan, size: 20, color: C.cyan });
  const mic = box(s, "VOICE", 880, 257, 205, 54, { fill: C.panel, lineColor: C.purple, size: 20, color: C.cyan2 });
  const ai = box(s, "AI / LLM", 880, 382, 205, 54, { fill: C.panel2, lineColor: C.purple, size: 20, color: C.white });
  const pc = box(s, "DESKTOP", 880, 507, 205, 54, { fill: C.panel, lineColor: C.lime, size: 20, color: C.lime });
  connect(s, user, mic, "bottom", "top", C.cyan); connect(s, mic, ai, "bottom", "top", C.purple); connect(s, ai, pc, "bottom", "top", C.lime);
  text(s, "Speech · Reasoning · Automation", 815, 590, 330, 28, { size: 16, color: C.muted, align: "center" });
  note(s, "Title slide. Replace student, guide, department, college and academic year placeholders before presenting.");
}

// 2. Introduction
{
  const s = presentation.slides.add(); base(s, 2, "1. Introduction", "Project overview");
  text(s, "JARVIS OS converts natural-language voice commands into practical computer actions.", 58, 142, 580, 55, { size: 25, bold: true, color: C.cyan2 });
  bullets(s, [
    "Traditional computer use depends on keyboard, mouse and graphical menus.",
    "Manual desktop operations can repeat the same steps across several applications.",
    "Voice interaction offers a natural way to request a task.",
    "JARVIS OS combines speech recognition, command analysis and desktop automation.",
    "Structured skills can act directly; AI/LLM processing supports configured intelligent interaction."
  ], 58, 220, 560, 345, { size: 20, spaceAfter: 9 });
  text(s, "Command workflow", 757, 144, 370, 28, { size: 20, bold: true, color: C.white, align: "center" });
  verticalFlow(s, ["User", "Voice Command", "Speech Recognition", "AI / LLM", "Intent & Task Analysis", "Desktop Automation", "Application / OS", "Response"], 755, 184, 370, 8, 42, [C.cyan, C.cyan, C.purple, C.purple, C.blue, C.lime, C.lime, C.cyan]);
  note(s, "Explain that commands can arrive as typed text or voice. High-confidence task skills handle direct commands; optional LLM providers support configured AI interactions.");
}

// 3. Literature review
{
  const s = presentation.slides.add(); base(s, 3, "2. Literature Review", "Existing assistants");
  text(s, "Existing assistants demonstrate voice interaction and AI assistance. JARVIS OS focuses on the desktop automation context.", 58, 142, 1120, 34, { size: 23, color: C.text });
  const t = s.tables.add({ rows: 6, columns: 3, left: 58, top: 202, width: 1164, height: 312, values: [
    ["System", "Main Capability", "Limitation in this project context"],
    ["Siri", "Voice assistance within the Apple ecosystem", "Desktop automation is outside this project’s Windows focus"],
    ["Google Assistant", "Voice queries, information and connected services", "Local desktop workflow control differs from this project’s goal"],
    ["Alexa", "Voice commands and skills", "Focus commonly extends to services and smart devices"],
    ["Microsoft Copilot", "AI assistance across Microsoft products", "Automation depends on available product permissions and integrations"],
    ["Traditional Python assistants", "Custom voice commands and scripted tasks", "Often rely on rule-based, project-specific command handling"]
  ]});
  t.styleOptions = { headerRow: true, bandedRows: true };
  t.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let r = 0; r < 6; r++) for (let c = 0; c < 3; c++) {
    const cell = t.getCell(r, c); cell.fill = r === 0 ? C.panel2 : (r % 2 ? "#0A1828" : C.panel);
    cell.text.style = { typeface: font, fontSize: r === 0 ? 18 : 16, bold: r === 0 || c === 0, color: r === 0 ? C.cyan2 : C.text, autoFit: "shrinkText" };
  }
  box(s, "Opportunity: Voice interaction + AI reasoning + computer automation in one desktop-focused system", 145, 555, 990, 56, { fill: C.panel2, lineColor: C.cyan, size: 21, color: C.white });
  text(s, "Comparison reflects the project scope. Capabilities vary by product, platform and version.", 172, 624, 940, 21, { size: 14, color: C.muted, align: "center" });
  note(s, "Literature-review comparison for presentation context. Avoid claiming that any named product has no desktop automation; feature availability changes by platform and version.");
}

// 4. Problem statement
{
  const s = presentation.slides.add(); base(s, 4, "3. Problem Statement", "Need for the system");
  text(s, "Problem statement", 72, 151, 300, 24, { size: 18, bold: true, color: C.cyan });
  box(s, "“To design and develop an intelligent voice-controlled desktop assistant, JARVIS OS, capable of understanding natural-language voice commands and performing computer operations, application control, web tasks, communication tasks, and AI-based question answering through an integrated desktop automation system.”", 70, 189, 670, 206, { fill: C.panel2, lineColor: C.cyan, size: 24, bold: false, color: C.white, align: "left", valign: "middle", insets: { top: 22, right: 26, bottom: 20, left: 26 } });
  text(s, "Major user challenges", 812, 151, 330, 24, { size: 18, bold: true, color: C.cyan });
  const issues = ["Manual navigation", "Repetitive operations", "Application switching", "Limited desktop control", "Rule-based language limits", "Cloud-service dependency"];
  issues.forEach((v, i) => {
    const x = 795 + (i % 2) * 205, y = 194 + Math.floor(i / 2) * 101;
    box(s, v, x, y, 185, 68, { fill: C.panel, lineColor: [C.cyan, C.blue, C.purple, C.lime, C.amber, C.red][i], size: 16, color: C.white });
  });
  box(s, "Design goal: reduce manual effort while keeping computer actions understandable and controlled.", 70, 468, 1075, 76, { fill: C.panel, lineColor: C.line, size: 24, color: C.cyan2 });
  note(s, "Read the problem statement as written, then briefly connect it to the six user challenges.");
}

// 5. Research gap
{
  const s = presentation.slides.add(); base(s, 5, "4. Research Gap", "From assistance to action");
  text(s, "Existing assistants commonly support voice recognition, question answering, web search and basic commands.", 58, 145, 1120, 34, { size: 22, color: C.text });
  const existing = verticalFlow(s, ["Existing Voice Assistant", "Voice Recognition", "Question Answering", "Basic Commands"], 160, 226, 350, 15, 55, [C.muted, C.muted, C.muted, C.muted]);
  const jarvis = verticalFlow(s, ["JARVIS OS", "Voice Recognition", "Natural-Language Understanding", "LLM Reasoning", "Task Planning", "Desktop Automation", "Real Computer Action"], 770, 192, 350, 9, 45, [C.cyan, C.cyan, C.purple, C.purple, C.blue, C.lime, C.lime]);
  text(s, "VERSUS", 576, 373, 130, 40, { size: 22, bold: true, color: C.amber, align: "center" });
  box(s, "Research/development gap: a desktop assistant that combines natural-language AI reasoning with actual computer automation while supporting flexible local and cloud AI processing.", 160, 577, 960, 60, { fill: C.panel2, lineColor: C.purple, size: 21, bold: false, color: C.white });
  note(s, "State the gap as a project-development need, rather than as an absolute claim about all other assistants.");
}

// 6. Aim and objectives
{
  const s = presentation.slides.add(); base(s, 6, "5. Aim and Objectives", "Project goals");
  box(s, "Aim: To develop an intelligent voice-controlled desktop assistant that uses Artificial Intelligence and desktop automation to understand natural-language commands and perform computer tasks efficiently.", 58, 143, 1164, 83, { fill: C.panel2, lineColor: C.cyan, size: 23, bold: false, color: C.white, align: "left", insets: { top: 15, right: 24, bottom: 12, left: 24 } });
  text(s, "Interaction and understanding", 75, 258, 470, 27, { size: 20, bold: true, color: C.cyan });
  text(s, "Automation and integration", 685, 258, 470, 27, { size: 20, bold: true, color: C.cyan });
  bullets(s, ["Develop a voice-based user interface", "Convert speech into text", "Understand natural-language commands", "Use an LLM for intelligent reasoning", "Provide text and voice responses", "Improve user productivity through automation"], 70, 299, 500, 285, { size: 20, spaceAfter: 9 });
  bullets(s, ["Execute commands automatically", "Open and control desktop applications", "Perform web searches and browser operations", "Automate communication-related tasks", "Integrate local and cloud AI models", "Support configurable AI fallback"], 680, 299, 500, 285, { size: 20, spaceAfter: 9 });
  statusLabel(s, "PLANNED / IMPLEMENTED", 516, 620, C.lime);
  note(s, "Use the objective slide to distinguish core project goals from optional services that depend on configuration, installed applications or internet access.");
}

// 7. Methodology
{
  const s = presentation.slides.add(); base(s, 7, "6. Methodology", "System architecture");
  text(s, "Architecture flow", 58, 142, 510, 24, { size: 19, bold: true, color: C.cyan });
  const user = box(s, "USER", 255, 173, 180, 38, { fill: C.panel2, lineColor: C.cyan, size: 16, color: C.cyan });
  const voice = box(s, "Voice Command", 230, 230, 230, 42, { fill: C.panel, lineColor: C.cyan, size: 17 });
  const stt = box(s, "Speech Recognition", 230, 293, 230, 42, { fill: C.panel, lineColor: C.cyan, size: 17 });
  const intent = box(s, "Command / Intent Analyzer", 196, 356, 298, 42, { fill: C.panel, lineColor: C.blue, size: 16 });
  const controller = box(s, "AI Controller", 235, 419, 220, 42, { fill: C.panel2, lineColor: C.purple, size: 17 });
  const ollama = box(s, "Ollama\nLocal AI", 98, 492, 180, 54, { fill: C.panel, lineColor: C.purple, size: 16, color: C.cyan2 });
  const nim = box(s, "NVIDIA NIM\nCloud AI", 412, 492, 180, 54, { fill: C.panel, lineColor: C.purple, size: 16, color: C.cyan2 });
  const planner = box(s, "Task Planner", 235, 571, 220, 42, { fill: C.panel2, lineColor: C.blue, size: 17 });
  connect(s, user, voice, "bottom", "top"); connect(s, voice, stt); connect(s, stt, intent); connect(s, intent, controller);
  connect(s, controller, ollama, "bottom", "top", C.purple, "elbow"); connect(s, controller, nim, "bottom", "top", C.purple, "elbow");
  connect(s, ollama, planner, "bottom", "left", C.blue, "elbow"); connect(s, nim, planner, "bottom", "right", C.blue, "elbow");
  const act = box(s, "Action / Automation", 760, 209, 290, 44, { fill: C.panel2, lineColor: C.lime, size: 18, color: C.lime });
  const windows = box(s, "Windows\nControl", 670, 337, 150, 56, { fill: C.panel, lineColor: C.lime, size: 16 });
  const browser = box(s, "Browser\nControl", 840, 337, 150, 56, { fill: C.panel, lineColor: C.lime, size: 16 });
  const apps = box(s, "Apps\nControl", 1010, 337, 150, 56, { fill: C.panel, lineColor: C.lime, size: 16 });
  const response = box(s, "Text / Voice Response", 820, 483, 210, 45, { fill: C.panel2, lineColor: C.cyan, size: 17 });
  connect(s, planner, act, "right", "left", C.lime, "elbow"); connect(s, act, windows, "bottom", "top", C.lime, "elbow"); connect(s, act, browser, "bottom", "top", C.lime); connect(s, act, apps, "bottom", "top", C.lime, "elbow");
  connect(s, windows, response, "bottom", "top", C.cyan, "elbow"); connect(s, browser, response, "bottom", "top", C.cyan); connect(s, apps, response, "bottom", "top", C.cyan, "elbow");
  text(s, "1 Voice input\n2 Speech-to-text\n3 Intent understanding\n4 AI processing\n5 Task planning\n6 Desktop automation\n7 Response", 760, 562, 350, 91, { size: 15, color: C.text, lineSpacing: 1.05 });
  note(s, "Architecture diagram. Ollama and NVIDIA NIM are selectable providers. The provider router supports configured automatic failover, subject to valid model/API configuration.");
}

// 8. System working
{
  const s = presentation.slides.add(); base(s, 8, "How JARVIS OS Works", "System working / examples");
  text(s, "Example 1", 70, 146, 250, 23, { size: 19, bold: true, color: C.cyan });
  box(s, "“Open Chrome and search for today’s weather.”", 70, 179, 520, 52, { fill: C.panel2, lineColor: C.cyan, size: 21, color: C.white, bold: false });
  verticalFlow(s, ["Voice", "Speech-to-Text", "Intent Detection", "Action Planning", "Open Chrome", "Enter Search Query", "Execute Search", "Response"], 170, 254, 320, 8, 36, [C.cyan, C.cyan, C.blue, C.blue, C.lime, C.lime, C.lime, C.cyan]);
  statusLabel(s, "IMPLEMENTED ROUTING", 265, 612, C.lime);
  text(s, "Example 2", 700, 146, 250, 23, { size: 19, bold: true, color: C.cyan });
  box(s, "“Open WhatsApp and send Rahul a message saying I’ll reach college in 20 minutes.”", 700, 179, 500, 72, { fill: C.panel2, lineColor: C.purple, size: 20, color: C.white, bold: false });
  const steps = ["Launch / focus WhatsApp", "Search for contact", "Type message", "Ask for confirmation", "Send message"];
  steps.forEach((v, i) => {
    const b = box(s, v, 748, 285 + i * 54, 405, 38, { fill: C.panel, lineColor: i === 3 ? C.amber : C.purple, size: 16, color: i === 3 ? C.amber : C.white });
    if (i) connect(s, s._whatsSteps?.[i - 1] ?? null, b);
    if (!s._whatsSteps) s._whatsSteps = []; s._whatsSteps.push(b);
  });
  statusLabel(s, "REQUIRES APP + CONFIRMATION", 853, 584, C.amber);
  text(s, "Actual behaviour depends on installed applications, access permissions and the current application interface.", 148, 634, 984, 20, { size: 14, color: C.muted, align: "center" });
  note(s, "Examples show intended routing. Present the WhatsApp flow only after explaining that it requires an available application, a focused window and a confirmation before sending.");
}

// 9. AI architecture
{
  const s = presentation.slides.add(); base(s, 9, "AI Architecture – Local + Cloud Fallback", "Provider routing");
  text(s, "Local processing", 120, 154, 270, 24, { size: 20, bold: true, color: C.cyan });
  const local = verticalFlow(s, ["Ollama", "Local LLM", "Privacy / offline-capable processing\nwhere supported"], 110, 194, 300, 15, 56, [C.purple, C.purple, C.cyan]);
  text(s, "Additional cloud capability", 820, 154, 340, 24, { size: 20, bold: true, color: C.cyan });
  const cloud = verticalFlow(s, ["NVIDIA NIM", "Cloud-hosted AI capability", "Response"], 800, 194, 300, 15, 56, [C.purple, C.purple, C.cyan]);
  const request = box(s, "User Request", 515, 198, 250, 44, { fill: C.panel2, lineColor: C.cyan, size: 18 });
  const controller = box(s, "AI Controller", 515, 280, 250, 44, { fill: C.panel, lineColor: C.purple, size: 18 });
  const tryLocal = box(s, "Try Local Model – Ollama", 480, 362, 320, 44, { fill: C.panel2, lineColor: C.purple, size: 18 });
  const success = box(s, "Success?", 535, 444, 210, 42, { fill: C.panel, lineColor: C.amber, size: 18, color: C.amber });
  const yes = box(s, "YES\nResponse", 440, 532, 150, 62, { fill: C.panel, lineColor: C.lime, size: 16, color: C.lime });
  const no = box(s, "NO\nNVIDIA NIM", 690, 532, 150, 62, { fill: C.panel, lineColor: C.red, size: 16, color: C.red });
  connect(s, request, controller); connect(s, controller, tryLocal); connect(s, tryLocal, success); connect(s, success, yes, "bottom", "top", C.lime, "elbow"); connect(s, success, no, "bottom", "top", C.red, "elbow");
  text(s, "Automatic failover is configuration-based. It operates when a fallback provider, valid credentials and AI_AUTO_FAILOVER are configured.", 170, 630, 940, 22, { size: 16, color: C.muted, align: "center" });
  note(s, "The code supports a provider router with optional automatic failover. Do not say that every request uses NVIDIA NIM. It is an optional configured provider.");
}

// 10. Expected outcomes
{
  const s = presentation.slides.add(); base(s, 10, "7. Expected Outcomes", "What the system delivers");
  text(s, "Functional outcomes", 110, 151, 380, 26, { size: 21, bold: true, color: C.cyan });
  const f = ["Voice command recognition", "Natural-language command routing", "Application launching", "Web searching and browser actions", "Desktop / system automation", "File and folder operations", "Communication automation", "Text and voice responses"];
  f.forEach((v, i) => { const x = 92 + (i % 2) * 250, y = 197 + Math.floor(i / 2) * 70; box(s, v, x, y, 225, 50, { fill: C.panel, lineColor: i < 4 ? C.cyan : C.lime, size: 15, color: C.white }); });
  text(s, "AI outcomes", 765, 151, 330, 26, { size: 21, bold: true, color: C.cyan });
  const a1 = box(s, "Ollama\nLocal AI", 760, 205, 190, 74, { fill: C.panel2, lineColor: C.purple, size: 19, color: C.cyan2 });
  const a2 = box(s, "NVIDIA NIM\nCloud capability", 1010, 205, 190, 74, { fill: C.panel2, lineColor: C.purple, size: 19, color: C.cyan2 });
  const a3 = box(s, "Configurable fallback\narchitecture", 885, 350, 190, 74, { fill: C.panel, lineColor: C.blue, size: 18, color: C.white });
  connect(s, a1, a3, "bottom", "top", C.purple, "elbow"); connect(s, a2, a3, "bottom", "top", C.purple, "elbow");
  box(s, "Result: a desktop assistant designed to understand a request, select a safe action and return a clear response.", 715, 498, 450, 76, { fill: C.panel2, lineColor: C.cyan, size: 20, color: C.white, bold: false });
  text(s, "Online services and optional AI features depend on the selected provider configuration.", 285, 623, 720, 20, { size: 15, color: C.muted, align: "center" });
  note(s, "Describe expected outcomes as a combination of implemented core capabilities and configurable services. Avoid claiming online/cloud services work without their setup.");
}

// 11. Plan of action
{
  const s = presentation.slides.add(); base(s, 11, "8. Plan of Action", "Development roadmap");
  const phases = ["Requirement\nAnalysis", "Literature\nReview", "System\nArchitecture", "Voice\nModule", "AI / LLM\nIntegration", "Ollama\nIntegration", "NVIDIA NIM\nIntegration", "Desktop\nAutomation", "Browser / App\nIntegration", "GUI\nDevelopment", "Testing &\nDebugging", "Final\nIntegration", "Documentation", "Final\nDemonstration"];
  text(s, "Roadmap from initial study to project demonstration", 58, 145, 650, 26, { size: 21, color: C.text });
  const pos = [];
  phases.forEach((p, i) => {
    const row = i < 7 ? 0 : 1, col = i % 7;
    const x = 63 + col * 168, y = 230 + row * 190;
    const b = box(s, `${String(i + 1).padStart(2, "0")}\n${p}`, x, y, 140, 82, { fill: row ? C.panel : C.panel2, lineColor: [C.cyan, C.blue, C.purple, C.lime, C.amber, C.cyan, C.purple][col], size: 15, color: C.white });
    pos.push(b);
    if (col > 0) connect(s, pos[i - 1], b, "right", "left", C.line);
  });
  connect(s, pos[6], pos[7], "bottom", "top", C.cyan, "elbow");
  text(s, "Each phase produces evidence for the next phase: design decisions, modules, integration results, tests, documentation and a live demonstration.", 150, 568, 980, 44, { size: 19, color: C.cyan2, align: "center" });
  note(s, "Use this roadmap as a proposed plan. Mark completed phases according to the team’s actual current status before presentation.");
}

// 12. components
{
  const s = presentation.slides.add(); base(s, 12, "9. List of Components", "Hardware and software");
  text(s, "Hardware", 83, 151, 350, 26, { size: 22, bold: true, color: C.cyan });
  bullets(s, ["Laptop or desktop computer", "Microphone", "Speakers or headphones", "Internet connection where online services are used"], 76, 197, 450, 220, { size: 21, spaceAfter: 10 });
  text(s, "Software", 658, 151, 350, 26, { size: 22, bold: true, color: C.cyan });
  bullets(s, ["Python with standard-library modules", "SpeechRecognition 3.17.0 and PyAudio 0.2.14", "Optional psutil for live system metrics", "HTML, CSS and JavaScript web HUD", "Windows PowerShell / ctypes for PC-control functions", "Ollama local LLM and NVIDIA NIM API support", ".env configuration and JSON local storage", "Native text-to-speech and configured browser"], 650, 197, 530, 350, { size: 19, spaceAfter: 7 });
  box(s, "Component choice follows a modular design: new skills and providers can be added without rebuilding the entire assistant.", 160, 585, 960, 54, { fill: C.panel2, lineColor: C.line, size: 20, color: C.cyan2, bold: false });
  note(s, "Component list uses the software libraries and modules provided in the supplied project requirements and source files.");
}

// 13. system requirements
{
  const s = presentation.slides.add(); base(s, 13, "System Requirements", "Deployment requirements");
  text(s, "Hardware requirements", 76, 151, 430, 26, { size: 21, bold: true, color: C.cyan });
  const hw = [
    ["Processor", "64-bit processor; local-model capacity depends on the selected Ollama model"],
    ["Memory", "No fixed minimum in the project; select RAM according to local-model size"],
    ["Storage", "Application files plus local-model storage where Ollama is used"],
    ["Audio", "Microphone for voice input; speakers/headphones for voice output"],
    ["Network", "Internet required for cloud AI and online services"]
  ];
  const ht = s.tables.add({ rows: 6, columns: 2, left: 70, top: 190, width: 520, height: 315, values: [["Item", "Requirement"], ...hw] });
  ht.styleOptions = { headerRow: true, bandedRows: true }; ht.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let r=0;r<6;r++) for (let c=0;c<2;c++) { const cell=ht.getCell(r,c); cell.fill=r===0?C.panel2:(r%2?"#0A1828":C.panel); cell.text.style={typeface:font,fontSize:r===0?17:15,bold:r===0||c===0,color:r===0?C.cyan2:C.text,autoFit:"shrinkText"}; }
  text(s, "Software requirements", 691, 151, 430, 26, { size: 21, bold: true, color: C.cyan });
  const sw = [
    ["Operating system", "Windows for the full PC-control feature set"],
    ["Python", "Python 3.x"],
    ["Packages", "SpeechRecognition 3.17.0; PyAudio 0.2.14; psutil"],
    ["Local AI", "Ollama plus a selected downloaded model, if enabled"],
    ["Cloud AI", "NVIDIA NIM API key, if enabled"],
    ["Browser", "Configured/default browser for web actions"]
  ];
  const st = s.tables.add({ rows: 7, columns: 2, left: 680, top: 190, width: 520, height: 355, values: [["Item", "Requirement"], ...sw] });
  st.styleOptions = { headerRow: true, bandedRows: true }; st.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let r=0;r<7;r++) for (let c=0;c<2;c++) { const cell=st.getCell(r,c); cell.fill=r===0?C.panel2:(r%2?"#0A1828":C.panel); cell.text.style={typeface:font,fontSize:r===0?17:15,bold:r===0||c===0,color:r===0?C.cyan2:C.text,autoFit:"shrinkText"}; }
  text(s, "Optional features require their own configuration and compatible hardware or services.", 190, 603, 900, 22, { size: 17, color: C.muted, align: "center" });
  note(s, "Requirements distinguish core execution from optional local AI, cloud AI, voice and online features. No fixed laptop specification is defined by the project.");
}

// 14 expenditure
{
  const s = presentation.slides.add(); base(s, 14, "10. Project Expenditure", "Cost estimate");
  text(s, "Use actual values in the ‘To be filled’ rows before final submission.", 58, 145, 900, 26, { size: 20, color: C.amber });
  const exp = [
    ["Laptop / PC", "Existing"], ["Microphone", "To be filled"], ["Internet / Data", "To be filled"],
    ["Software / open-source libraries", "₹0"], ["Python", "₹0"], ["Ollama", "₹0"],
    ["Development tools", "₹0"], ["NVIDIA NIM API", "Optional; usage-based if enabled"], ["Miscellaneous", "To be filled"], ["Total", "To be filled"]
  ];
  const t = s.tables.add({ rows: 11, columns: 2, left: 190, top: 190, width: 900, height: 390, values: [["Component", "Approximate Cost"], ...exp] });
  t.styleOptions = { headerRow: true, bandedRows: true, totalRow: true }; t.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let r=0;r<11;r++) for (let c=0;c<2;c++) { const cell=t.getCell(r,c); const isHead=r===0, isTotal=r===10; cell.fill=isHead?C.panel2:(isTotal?"#113553":(r%2?"#0A1828":C.panel)); cell.text.style={typeface:font,fontSize:isHead?19:17,bold:isHead||isTotal||c===0,color:isHead?C.cyan2:(isTotal?C.white:C.text),autoFit:"shrinkText"}; }
  text(s, "The deck preserves unknown costs as placeholders instead of inventing expenses.", 235, 613, 810, 22, { size: 16, color: C.muted, align: "center" });
  note(s, "Fill actual microphone, internet and miscellaneous expenditure values. The total must be calculated from those completed rows.");
}

// 15 advantages
{
  const s = presentation.slides.add(); base(s, 15, "Advantages", "Project benefits");
  const values = ["Natural voice interaction", "Hands-free computer interaction", "Automation of repetitive tasks", "AI-powered reasoning", "Local AI capability", "Extensible architecture", "Faster task execution", "Multiple application integration", "Multi-step command support", "Reduced manual operations"];
  values.forEach((v,i) => { const col=i%2,row=Math.floor(i/2); const x=112+col*540,y=165+row*84; box(s, v, x,y,455,58,{fill:row%2?C.panel:C.panel2,lineColor:[C.cyan,C.blue,C.purple,C.lime,C.amber][row],size:20,color:C.white}); });
  text(s, "The system’s modular structure also supports future skills, providers and integrations.", 192, 617, 900, 24, { size: 18, color: C.cyan2, align: "center" });
  note(s, "Advantages reflect the intended user value of combining voice input with structured desktop automation.");
}

// 16 limitations
{
  const s = presentation.slides.add(); base(s, 16, "Limitations", "Current constraints");
  const values = [
    ["Voice recognition", "Background noise and microphone quality can affect speech recognition."],
    ["Automation", "Some actions depend on application interfaces, window focus and permissions."],
    ["Cloud services", "Internet access is required for cloud AI and online services."],
    ["AI output", "AI responses can sometimes be incorrect or incomplete."],
    ["Hardware", "Performance depends on local hardware and selected AI model size."],
    ["Application changes", "UI updates can affect keyboard- and screen-based automation."]
  ];
  values.forEach((pair,i)=>{ const col=i%2,row=Math.floor(i/2),x=78+col*580,y=172+row*135; box(s,"",x,y,530,103,{fill:C.panel,lineColor:[C.amber,C.red,C.purple][row]}); text(s,pair[0],x+20,y+15,480,24,{size:19,bold:true,color:C.cyan2}); text(s,pair[1],x+20,y+47,480,40,{size:16,color:C.text}); });
  box(s, "Responsible use: maintain confirmations for sensitive actions and verify outcomes before treating a task as complete.", 160, 602, 960, 48, { fill: C.panel2, lineColor: C.amber, size: 18, color: C.amber, bold: false });
  note(s, "Limitations should be presented openly. Explain that controls and confirmations help reduce risk but cannot guarantee every external application outcome.");
}

// 17 future scope
{
  const s = presentation.slides.add(); base(s, 17, "Future Scope", "Possible enhancements");
  const roadmap = ["Multi-agent architecture", "Long-term context and memory", "More operating-system support", "Additional application integrations", "Improved offline capabilities", "Computer vision and screen understanding", "Autonomous task planning", "Mobile and device integration", "Personalized workflows", "Security and permission management"];
  roadmap.forEach((v,i)=>{ const col=i%2,row=Math.floor(i/2),x=112+col*540,y=170+row*84; box(s,v,x,y,455,58,{fill:row%2?C.panel:C.panel2,lineColor:[C.cyan,C.blue,C.purple,C.lime,C.amber][row],size:19,color:C.white}); });
  text(s, "Future work can extend the assistant from command execution toward more context-aware and permission-aware automation.", 160, 616, 960, 30, { size: 19, color: C.cyan2, align: "center" });
  note(s, "Future-scope items are proposals, not claims about the current version.");
}

// 18 conclusion
{
  const s = presentation.slides.add(); base(s, 18, "Conclusion", "Project summary");
  box(s, "JARVIS OS demonstrates how Artificial Intelligence, speech recognition and desktop automation can be combined to create a more natural computer interaction system.", 120, 175, 1040, 95, { fill: C.panel2, lineColor: C.cyan, size: 27, bold: false, color: C.white });
  box(s, "The system is designed to interpret user commands and translate them into practical computer actions, rather than only answering questions.", 120, 312, 1040, 82, { fill: C.panel, lineColor: C.blue, size: 24, bold: false, color: C.cyan2 });
  box(s, "Local and cloud AI providers offer a flexible architecture when configured, while modular automation skills support future expansion.", 120, 435, 1040, 82, { fill: C.panel2, lineColor: C.purple, size: 24, bold: false, color: C.white });
  text(s, "JARVIS OS: intelligent assistance connected to practical desktop action.", 180, 584, 920, 34, { size: 24, bold: true, color: C.lime, align: "center" });
  note(s, "Conclude with the project’s central idea: voice or text request, command understanding, action selection and a clear response.");
}

// 19 demo
{
  const s = presentation.slides.add(); base(s, 19, "JARVIS OS – Live Demonstration", "Demonstration workflow");
  const steps = ["Speak", "Understand", "Plan", "Execute", "Respond"];
  const flows=[]; steps.forEach((v,i)=>{ const b=box(s,v,112+i*212,160,165,55,{fill:i%2?C.panel:C.panel2,lineColor:[C.cyan,C.blue,C.purple,C.lime,C.cyan][i],size:21,color:C.white}); flows.push(b); if(i)connect(s,flows[i-1],b,"right","left",C.cyan); });
  text(s,"Screenshot placeholders",70,276,320,24,{size:19,bold:true,color:C.cyan});
  const ph1=box(s,"INSERT SCREENSHOT\nWeb HUD / dashboard",70,315,350,205,{fill:"#081827",lineColor:C.cyan,size:20,color:C.cyan2});
  const ph2=box(s,"INSERT SCREENSHOT\nCommand response",465,315,350,205,{fill:"#081827",lineColor:C.purple,size:20,color:C.cyan2});
  const ph3=box(s,"INSERT SCREENSHOT\nAutomation result",860,315,350,205,{fill:"#081827",lineColor:C.lime,size:20,color:C.cyan2});
  text(s,"Suggested live commands: status   |   open chrome and search for weather   |   set a 1 minute timer   |   voice",94,575,1090,26,{size:17,color:C.text,align:"center"});
  text(s,"Replace placeholders with actual screenshots before final presentation.",260,623,760,20,{size:15,color:C.amber,align:"center"});
  note(s,"Demo slide. Insert team screenshots after running the application. Use safe commands for a live demo and avoid showing keys, passwords or personal chats.");
}

// 20 thank you
{
  const s = presentation.slides.add();
  s.background.fill = C.bg;
  shape(s, "rect", 0, 0, W, 8, C.cyan, { style: "solid", fill: C.cyan, width: 0 });
  text(s, "JARVIS OS", 270, 156, 740, 65, { size: 58, bold: true, color: C.white, align: "center" });
  text(s, "Intelligent Voice-Controlled Desktop Assistant", 270, 239, 740, 40, { size: 27, color: C.cyan2, align: "center" });
  const q = box(s, "Q&A", 525, 352, 230, 92, { fill: C.panel2, lineColor: C.cyan, size: 38, color: C.cyan });
  text(s, "Thank You", 270, 492, 740, 54, { size: 43, bold: true, color: C.white, align: "center" });
  text(s, "Questions & Answers", 270, 554, 740, 28, { size: 21, color: C.text, align: "center" });
  text(s, "JARVIS OS – Intelligent Voice-Controlled Desktop Assistant", 220, 674, 840, 20, { size: 12, color: C.muted, align: "center" });
  note(s, "Thank the audience and invite questions.");
}

const candidatePath = path.join(TMP_DIR, "JARVIS_OS_Project_Presentation_draft.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 20,
  requiredNativeTableOwnerSlides: [3, 13, 14],
};
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit", "--require-native-table-slide", "3", "--require-native-table-slide", "13", "--require-native-table-slide", "14"],
  fontPolicy: { basis: "design", families: [font] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(TMP_DIR, "JARVIS_OS_Project_Presentation_v2.validation.json"),
});
console.log(JSON.stringify({ finalPath: FINAL_PPTX, font, result }, null, 2));
