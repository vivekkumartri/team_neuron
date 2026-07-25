import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles, Wand2, GitBranch, BookOpen, Image as ImageIcon, LayoutGrid,
  Users, Skull, RotateCcw, MapPin, Plus, X, Check, ChevronRight,
  Download, RefreshCw, Edit3, Zap, Clock, Layers, Film, Heart,
  Brain, Wind, ArrowRight, Trash2, UserPlus, Sparkle, Flame, Trophy, Lock,
  ShieldCheck, ShieldAlert, TrendingUp, MessageSquare, Clapperboard,
  AlertTriangle, Gauge
} from "lucide-react";

/* ============================================================================
   STORY ENGINE — clickable pitch prototype
   Dummy-data only. No backend calls. Every "generate" action fakes a short
   loading beat so the flow feels alive, then resolves to canned content.
============================================================================ */

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

.se-root {
  --bg: #0B0E1A;
  --bg-elevated: #12172A;
  --panel: #171D33;
  --card: #1D2440;
  --card-border: #2A3255;
  --parchment: #F3EEE0;
  --parchment-dim: #E4DCC6;
  --ink: #EAE6DA;
  --ink-dim: #9AA1C2;
  --ink-faint: #616A93;
  --amber: #E8A33D;
  --amber-dim: #7A5A22;
  --violet: #8C6BFF;
  --violet-dim: rgba(140,107,255,0.18);
  --rose: #D1544A;
  --teal: #4FC3B0;
  font-family: 'Inter', sans-serif;
  background: var(--bg);
  color: var(--ink);
  min-height: 100vh;
  display: flex;
  position: relative;
}
.se-root * { box-sizing: border-box; }
.se-serif { font-family: 'Fraunces', serif; }
.se-mono { font-family: 'IBM Plex Mono', monospace; }

.se-root a, .se-root button { font-family: inherit; }

/* --- nav --- */
.se-nav {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-elevated);
  border-right: 1px solid var(--card-border);
  padding: 28px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.se-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
  padding: 0 6px;
}
.se-dial {
  width: 30px; height: 30px; flex-shrink: 0;
}
.se-brand-name {
  font-size: 15px;
  letter-spacing: 0.02em;
  font-weight: 600;
  color: var(--ink);
}
.se-brand-tag {
  font-size: 10px;
  color: var(--ink-faint);
  font-family: 'IBM Plex Mono', monospace;
  letter-spacing: 0.06em;
}
.se-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink-dim);
  text-align: left;
  transition: all 0.15s ease;
}
.se-nav-item:hover { background: var(--panel); color: var(--ink); }
.se-nav-item.active {
  background: var(--card);
  border-color: var(--card-border);
  color: var(--ink);
}
.se-nav-num {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--amber);
  width: 22px;
  flex-shrink: 0;
}
.se-nav-item.active .se-nav-num { color: var(--amber); }
.se-nav-label { font-size: 13px; font-weight: 500; }
.se-nav-foot {
  margin-top: auto;
  padding: 12px 10px;
  font-size: 10.5px;
  color: var(--ink-faint);
  border-top: 1px solid var(--card-border);
  line-height: 1.5;
}

/* --- main --- */
.se-main {
  flex: 1;
  min-width: 0;
  padding: 40px 48px 80px;
  max-width: 1240px;
}
.se-eyebrow {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--amber);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.se-eyebrow::before {
  content: '';
  width: 16px; height: 1px;
  background: var(--amber-dim);
}
.se-h1 {
  font-family: 'Fraunces', serif;
  font-size: 34px;
  font-weight: 600;
  line-height: 1.15;
  margin: 0 0 8px;
  color: var(--ink);
}
.se-sub {
  color: var(--ink-dim);
  font-size: 14px;
  max-width: 640px;
  line-height: 1.6;
  margin-bottom: 32px;
}

.se-card {
  background: var(--card);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 22px;
}
.se-section-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
  text-transform: uppercase;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* form bits */
.se-radio-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 22px; }
.se-radio {
  padding: 9px 15px;
  border-radius: 999px;
  border: 1px solid var(--card-border);
  background: var(--panel);
  color: var(--ink-dim);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex; align-items: center; gap: 6px;
}
.se-radio:hover { border-color: var(--ink-faint); }
.se-radio.active {
  background: var(--violet-dim);
  border-color: var(--violet);
  color: var(--ink);
}
.se-radio.active .se-dot { background: var(--violet); }
.se-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ink-faint); }

.se-textarea {
  width: 100%;
  min-height: 120px;
  background: var(--panel);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  color: var(--ink);
  padding: 14px 16px;
  font-size: 14px;
  font-family: 'Inter', sans-serif;
  line-height: 1.6;
  resize: vertical;
}
.se-textarea:focus, .se-input:focus { outline: 2px solid var(--violet); outline-offset: 1px; }
.se-charcount { font-size: 11px; color: var(--ink-faint); margin-top: 6px; font-family: 'IBM Plex Mono', monospace; }

.se-pill-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 22px; }
.se-pill {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--card-border);
  background: var(--panel);
  color: var(--ink-dim);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.se-pill.active {
  background: rgba(232,163,61,0.14);
  border-color: var(--amber);
  color: var(--amber);
}

.se-select {
  background: var(--panel);
  border: 1px solid var(--card-border);
  color: var(--ink);
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.se-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 22px;
  border-radius: 9px;
  border: none;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.se-btn-primary {
  background: linear-gradient(135deg, var(--amber), #C97B2E);
  color: #1A1204;
}
.se-btn-primary:hover { filter: brightness(1.08); transform: translateY(-1px); }
.se-btn-ghost {
  background: transparent;
  border: 1px solid var(--card-border);
  color: var(--ink-dim);
}
.se-btn-ghost:hover { border-color: var(--ink-faint); color: var(--ink); }
.se-btn-violet {
  background: var(--violet);
  color: white;
}
.se-btn-violet:hover { filter: brightness(1.1); }
.se-btn-danger { background: rgba(209,84,74,0.15); color: var(--rose); border: 1px solid rgba(209,84,74,0.4); }
.se-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }
.se-btn-sm { padding: 7px 12px; font-size: 12px; border-radius: 7px; }

.se-loading {
  display: flex; align-items: center; gap: 10px;
  color: var(--ink-dim); font-size: 13px;
  font-family: 'IBM Plex Mono', monospace;
}
.se-spin { animation: se-rotate 1s linear infinite; }
@keyframes se-rotate { to { transform: rotate(360deg); } }

/* concept cards */
.se-concept-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 22px; }
.se-concept-card {
  background: var(--card);
  border: 1.5px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex; flex-direction: column; gap: 12px;
}
.se-concept-card:hover { border-color: var(--ink-faint); }
.se-concept-card.selected {
  border-color: var(--amber);
  background: linear-gradient(180deg, rgba(232,163,61,0.08), var(--card) 40%);
  box-shadow: 0 0 0 1px var(--amber), 0 8px 28px rgba(232,163,61,0.12);
}
.se-concept-title { font-family: 'Fraunces', serif; font-size: 18px; font-weight: 600; margin: 0; }
.se-concept-tag { font-size: 12.5px; color: var(--amber); font-style: italic; }
.se-concept-summary { font-size: 12.5px; color: var(--ink-dim); line-height: 1.6; }
.se-concept-conflict-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; margin-top: 4px;}
.se-entity-chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; padding: 4px 8px; border-radius: 6px;
  background: var(--panel); color: var(--ink-dim); margin: 3px 4px 0 0;
  border: 1px solid var(--card-border);
}

/* badges */
.se-badge {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  padding: 3px 8px;
  border-radius: 5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  display: inline-flex; align-items: center; gap: 5px;
}
.se-badge-active { background: rgba(79,195,176,0.15); color: var(--teal); }
.se-badge-deceased { background: rgba(209,84,74,0.15); color: var(--rose); }
.se-badge-draft { background: rgba(140,107,255,0.15); color: var(--violet); }
.se-badge-published { background: rgba(232,163,61,0.15); color: var(--amber); }
.se-badge-exiled { background: rgba(154,161,194,0.15); color: var(--ink-dim); }

/* workspace split */
.se-split { display: grid; grid-template-columns: 1fr 1.15fr; gap: 20px; align-items: start; }
.se-graph-panel {
  background: var(--bg-elevated);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 16px;
  min-height: 480px;
  position: relative;
  background-image: radial-gradient(circle, rgba(255,255,255,0.035) 1px, transparent 1px);
  background-size: 22px 22px;
}
.se-reader-panel {
  background: var(--parchment);
  color: #201A0F;
  border-radius: 14px;
  padding: 26px 28px;
  min-height: 480px;
}
.se-reader-panel .se-eyebrow { color: #A9701F; }
.se-reader-title { font-family: 'Fraunces', serif; font-size: 22px; font-weight: 600; margin-bottom: 14px; color: #201A0F; }
.se-reader-text { font-size: 14.5px; line-height: 1.85; color: #3A3122; font-family: 'Fraunces', serif; font-weight: 400; }
.se-reader-text p { margin: 0 0 14px; }
.se-reader-textarea {
  width: 100%; min-height: 180px; font-family: 'Fraunces', serif; font-size: 14.5px; line-height: 1.85;
  background: #FBF8F0; border: 1px solid #D9CDA9; border-radius: 8px; padding: 14px; color: #3A3122;
}
.se-choice {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px; border-radius: 9px;
  border: 1.5px solid #D9CDA9; margin-bottom: 8px; cursor: pointer;
  background: #FBF8F0; font-size: 13.5px; color: #3A3122; transition: all 0.15s ease;
}
.se-choice.selected { border-color: #A9701F; background: #F3E6C8; }
.se-choice-radio { width: 15px; height: 15px; border-radius: 50%; border: 1.5px solid #A9701F; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.se-choice-radio.on::after { content: ''; width: 7px; height: 7px; border-radius: 50%; background: #A9701F; }
.se-choice-input { flex: 1; border: none; background: transparent; font-size: 13.5px; color: #3A3122; font-family: 'Inter', sans-serif; }
.se-choice-input:focus { outline: none; }

/* entity node styles */
.se-node {
  position: absolute;
  padding: 10px 13px;
  border-radius: 10px;
  background: var(--card);
  border: 1.5px solid var(--card-border);
  width: 148px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.se-node:hover { border-color: var(--ink-faint); }
.se-node.active-glow { border-color: var(--amber); box-shadow: 0 0 0 1px var(--amber), 0 0 18px rgba(232,163,61,0.35); }
.se-node.deceased { opacity: 0.42; filter: grayscale(0.6); }
.se-node-name { font-size: 12.5px; font-weight: 600; color: var(--ink); margin-bottom: 3px; }
.se-node-role { font-size: 10px; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; }

/* table */
.se-table { width: 100%; border-collapse: collapse; }
.se-table th {
  text-align: left; font-family: 'IBM Plex Mono', monospace; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint);
  padding: 10px 12px; border-bottom: 1px solid var(--card-border);
}
.se-table td { padding: 12px; border-bottom: 1px solid var(--card-border); font-size: 13px; vertical-align: middle; }
.se-table tr:last-child td { border-bottom: none; }

/* comic grid */
.se-comic-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.se-panel-card {
  border-radius: 12px; overflow: hidden; border: 1px solid var(--card-border); background: var(--card);
}
.se-panel-art {
  height: 168px; position: relative; display: flex; align-items: flex-end; padding: 12px;
  color: rgba(255,255,255,0.85);
}
.se-panel-body { padding: 12px 14px; }
.se-panel-caption { font-size: 12px; color: var(--ink-dim); font-style: italic; }
.se-panel-speech {
  font-size: 12.5px; background: white; color: #201A0F; padding: 8px 10px;
  border-radius: 10px 10px 10px 2px; display: inline-block; margin-top: 6px; font-weight: 600;
}

/* timeline */
.se-timeline-track { display: flex; align-items: flex-start; gap: 0; overflow-x: auto; padding: 22px 6px 10px; }
.se-tl-node {
  min-width: 168px; background: var(--card); border: 1.5px solid var(--card-border);
  border-radius: 12px; padding: 14px; margin-right: 34px; position: relative; flex-shrink: 0;
}
.se-tl-node.branch { border-style: dashed; opacity: 0.85; margin-top: 18px; }
.se-tl-arrow {
  position: absolute; top: 48%; right: -34px; color: var(--ink-faint); font-size: 16px;
}
.se-tl-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }

/* sandbox */
.se-realm-flow { display: flex; align-items: center; gap: 14px; }

/* arc options */
.se-arc-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 26px; }
.se-obj-tag {
  display: inline-flex; align-items: center; gap: 6px; background: var(--panel);
  border: 1px solid var(--card-border); border-radius: 999px; padding: 6px 12px; font-size: 12px;
  color: var(--ink-dim); margin: 0 8px 8px 0;
}
.se-obj-tag button { background: none; border: none; color: var(--ink-faint); cursor: pointer; display:flex; }

.se-two-col { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; }
.se-flex-between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.se-mt { margin-top: 22px; }
.se-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 18px; margin-bottom: 22px; border-bottom: 1px solid var(--card-border);
}
.se-topbar-left { display: flex; align-items: center; gap: 14px; font-size: 13px; color: var(--ink-dim); }
.se-topbar-title { font-family: 'Fraunces', serif; font-size: 17px; font-weight: 600; color: var(--ink); }

/* --- seeding wizard --- */
.se-wizard { max-width: 620px; margin: 0 auto; }
.se-wizard-progress { display: flex; align-items: center; gap: 8px; margin-bottom: 34px; }
.se-wizard-dot {
  flex: 1; height: 3px; border-radius: 3px; background: var(--card-border); transition: background 0.3s ease;
}
.se-wizard-dot.done { background: var(--amber); }
.se-wizard-dot.current { background: var(--violet); }
.se-wizard-stepnum {
  font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-faint);
  letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px;
}
.se-wizard-q {
  font-family: 'Fraunces', serif; font-size: 26px; font-weight: 600; margin: 0 0 8px; line-height: 1.25;
}
.se-wizard-hint { color: var(--ink-dim); font-size: 13.5px; margin-bottom: 26px; line-height: 1.6; }
.se-wizard-body { animation: se-step-in 0.3s ease; min-height: 220px; }
@keyframes se-step-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

.se-option-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.se-option-card {
  background: var(--card); border: 1.5px solid var(--card-border); border-radius: 12px;
  padding: 18px; cursor: pointer; transition: all 0.15s ease; text-align: left;
}
.se-option-card:hover { border-color: var(--ink-faint); }
.se-option-card.selected { border-color: var(--amber); background: rgba(232,163,61,0.08); box-shadow: 0 0 0 1px var(--amber); }
.se-option-icon {
  width: 34px; height: 34px; border-radius: 9px; background: var(--panel);
  display: flex; align-items: center; justify-content: center; margin-bottom: 12px; color: var(--amber);
}
.se-option-card.selected .se-option-icon { background: rgba(232,163,61,0.18); }
.se-option-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.se-option-desc { font-size: 12px; color: var(--ink-faint); line-height: 1.5; }

.se-wizard-textarea {
  width: 100%; min-height: 160px; background: var(--panel); border: 1.5px solid var(--card-border);
  border-radius: 12px; color: var(--ink); padding: 18px; font-size: 15.5px; line-height: 1.7;
  font-family: 'Fraunces', serif;
}
.se-wizard-textarea:focus { outline: none; border-color: var(--violet); }

.se-tag-cluster { margin-bottom: 24px; }
.se-tag-cluster-label { font-size: 11.5px; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }

.se-review-row {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
  padding: 12px 0; border-bottom: 1px solid var(--card-border); font-size: 13px;
}
.se-review-row:last-child { border-bottom: none; }
.se-review-key { color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; flex-shrink: 0; width: 90px; padding-top: 2px; }
.se-review-val { color: var(--ink); text-align: right; line-height: 1.5; }

.se-wizard-nav { display: flex; justify-content: space-between; align-items: center; margin-top: 30px; }
.se-skip-link { background: none; border: none; color: var(--ink-faint); font-size: 12.5px; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.se-skip-link:hover { color: var(--ink-dim); }

@media (max-width: 980px) {
  .se-split, .se-two-col, .se-concept-grid, .se-comic-grid, .se-arc-grid { grid-template-columns: 1fr; }
  .se-option-grid { grid-template-columns: 1fr; }
  .se-nav { display: none; }
  .se-main { padding: 24px; }
}

/* --- character cast setup --- */
.se-cast-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-bottom: 18px; }
.se-cast-card { background: var(--card); border: 1.5px solid var(--card-border); border-radius: 14px; padding: 18px; }
.se-cast-card.locked { border-style: dashed; opacity: 0.92; }
.se-cast-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.se-cast-field-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; margin: 10px 0 4px; }
.se-cast-input {
  width: 100%; background: var(--panel); border: 1px solid var(--card-border); border-radius: 7px;
  color: var(--ink); padding: 8px 10px; font-size: 12.5px; font-family: 'Inter', sans-serif;
}
.se-lock-pill {
  display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; padding: 3px 9px;
  border-radius: 999px; background: rgba(154,161,194,0.15); color: var(--ink-dim);
  font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.04em;
}
.se-lock-pill.new { background: rgba(79,195,176,0.15); color: var(--teal); }

.se-hidden-row {
  margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--card-border);
}
.se-hidden-label {
  display: flex; align-items: center; gap: 5px; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--rose); font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px;
}
.se-hidden-line {
  font-size: 12.5px; line-height: 1.5; color: var(--ink-dim); margin: 0;
  filter: blur(5px); user-select: none; -webkit-user-select: none; cursor: default;
  transition: filter 0.2s ease;
}
.se-hidden-note {
  font-size: 10.5px; color: var(--ink-faint); margin-top: 5px; font-style: italic;
}

/* --- screenplay reader --- */
.se-slugline {
  font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 12.5px;
  letter-spacing: 0.03em; color: #6E5A22; text-transform: uppercase; margin: 18px 0 8px;
}
.se-slugline:first-child { margin-top: 0; }
.se-scene-action { font-size: 13.5px; line-height: 1.8; color: #4A3F2C; font-style: italic; margin: 0 0 12px; }
.se-dialogue-block { max-width: 340px; margin: 0 auto 16px; text-align: center; }
.se-dialogue-character { font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 700; letter-spacing: 0.04em; color: #201A0F; }
.se-dialogue-paren { font-size: 11px; font-style: italic; color: #8A6E2E; margin-top: 1px; }
.se-dialogue-line { font-size: 14px; line-height: 1.6; color: #3A3122; margin-top: 2px; }

/* --- choice / conversation log --- */
.se-choicelog { background: #FBF8F0; border: 1px solid #D9CDA9; border-radius: 10px; padding: 12px 14px; margin-bottom: 16px; }
.se-choicelog-item { display: flex; gap: 8px; font-size: 12px; color: #5A4C2E; padding: 4px 0; }
.se-choicelog-chap { font-family: 'IBM Plex Mono', monospace; font-weight: 700; color: #8A6E2E; flex-shrink: 0; }

/* --- agents screen --- */
.se-agent-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.se-agent-card { background: var(--card); border: 1.5px solid var(--card-border); border-radius: 14px; padding: 22px; }
.se-agent-head { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.se-agent-title { font-family: 'Fraunces', serif; font-size: 17px; font-weight: 600; }
.se-agent-sub { font-size: 12px; color: var(--ink-faint); margin-bottom: 16px; }
.se-sync-row { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--card-border); }
.se-sync-row:last-child { border-bottom: none; }
.se-sync-name { font-size: 13px; font-weight: 600; margin-bottom: 2px; }
.se-sync-note { font-size: 12px; color: var(--ink-dim); line-height: 1.5; }
.se-score-big { font-family: 'Fraunces', serif; font-size: 44px; font-weight: 700; line-height: 1; color: var(--amber); }
.se-score-label { font-size: 11px; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; }
.se-score-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.se-score-bar-track { flex: 1; height: 6px; border-radius: 4px; background: var(--panel); overflow: hidden; }
.se-score-bar-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--violet), var(--amber)); }
.se-score-bar-label { font-size: 11.5px; color: var(--ink-dim); width: 128px; flex-shrink: 0; }
.se-score-bar-val { font-size: 11.5px; color: var(--ink-faint); font-family: 'IBM Plex Mono', monospace; width: 30px; text-align: right; }
.se-agent-topchip {
  display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 8px;
  font-size: 11.5px; font-family: 'IBM Plex Mono', monospace; border: 1px solid var(--card-border);
  background: var(--panel); color: var(--ink-dim); cursor: pointer;
}
`;


/* ---------------------------------------------------------------------- */
/* Dummy data                                                              */
/* ---------------------------------------------------------------------- */

const CONCEPTS = [
  {
    id: "concept_1",
    title: "Chrono-Shards of Neon",
    tagline: "Time is a currency, and the bank is bleeding.",
    summary:
      "In a subterranean metropolis where time is mined from crystalline deposits, a rogue watchmaker accidentally binds his soul to a sentient temporal artifact.",
    coreConflict:
      "The Watchmaker Guild wants to destroy the artifact, while an AI syndicate wants to use it to freeze the city in perpetual night.",
    entities: [
      { name: "Kaelen", type: "Humanoid · Protagonist" },
      { name: "Dial of Anos", type: "Artifact · Sentient" },
      { name: "Chrono-Spire", type: "Location" },
    ],
  },
  {
    id: "concept_2",
    title: "Echoes of the Spire",
    tagline: "The sky is falling, one hour at a time.",
    summary:
      "A tower built of glass and stolen hours houses the last monks who can read the sun. When solar flares scramble their calendar, the city's memory begins to unravel.",
    coreConflict: "Solar flares versus the Monastic Order guarding the Spire's clockwork heart.",
    entities: [
      { name: "Lyra", type: "Humanoid · Stargazer" },
      { name: "Glass Spire", type: "Location" },
      { name: "The Flare Choir", type: "Sentient AI" },
    ],
  },
  {
    id: "concept_3",
    title: "Clockwork Abyss",
    tagline: "Below the gears, something keeps perfect time.",
    summary:
      "A deep-ocean city of cogwheels and pressure-forged brass is stalked by a leviathan built from every clock ever thrown into the sea.",
    coreConflict: "A mechanical leviathan versus the scavenger fleets who salvage its shed gears for fuel.",
    entities: [
      { name: "Vane", type: "Humanoid · Diver" },
      { name: "Iron Tooth", type: "Object · Submarine" },
      { name: "The Leviathan", type: "Creature" },
    ],
  },
];

const ENTITIES = [
  { id: "e1", name: "Kaelen", role: "Rogue Watchmaker", type: "HUMANOID", status: "ACTIVE", location: "Sector 4", x: 60, y: 60, visual: "Grease-stained hands, long coat, tired eyes" },
  { id: "e2", name: "Dial of Anos", role: "Sentient Temporal Relic", type: "OBJECT_ARTIFACT", status: "ACTIVE", location: "Sector 4", x: 300, y: 60, visual: "Glowing amber runes, dark matte steel" },
  { id: "e3", name: "Chrono-Spire", role: "Guild Headquarters", type: "LOCATION_BUILDING", status: "ACTIVE", location: "Upper Ring", x: 300, y: 230, visual: "Glass and brass, lit by mined time-crystal" },
  { id: "e4", name: "Watchmaker Guild", role: "Antagonist Faction", type: "SENTIENT_AI", status: "ACTIVE", location: "Chrono-Spire", x: 60, y: 230, visual: "Cloaked overseers, ticking masks" },
];

const RELATIONSHIPS = [
  { from: "e1", to: "e2", label: "WIELDER_OF" },
  { from: "e2", to: "e3", label: "LOCATED_IN" },
  { from: "e1", to: "e4", label: "ENEMY_OF" },
];

const CHAPTER1 = {
  title: "The First Clockwork Dial",
  paragraphs: [
    "The rain in Sector 4 smelled of rusted copper and ozone. Kaelen wiped his grease-stained hands on a rag that had stopped being white years ago, watching the drips race each other down a window that hadn't been clean since before the Guild sealed the upper ring.",
    "He gripped the Dial of Anos tight. Its glowing runes hummed against his pulse, a rhythm that didn't match his own — slower, older, patient in a way nothing in Sector 4 had any right to be.",
    "Somewhere above, the Watchmaker Guild would already know it was gone. They always knew. The only question left was how many hours he had before they came looking, and whether the Dial itself was counting them down for him.",
  ],
};

const CHOICES = [
  { id: "c1", text: "Activate the Dial's runes and listen to what it's trying to say." },
  { id: "c2", text: "Hide it in your coat and disappear into the crowd." },
];

const PANEL_ART = [
  "linear-gradient(135deg, #2A2140 0%, #4A2E4F 55%, #C4633B 100%)",
  "linear-gradient(135deg, #1B2A3C 0%, #2E4B5E 60%, #E8A33D 130%)",
  "linear-gradient(135deg, #1A1420 0%, #3B2140 60%, #7A2E3B 120%)",
  "linear-gradient(135deg, #10182A 0%, #253A55 55%, #4FC3B0 130%)",
];

const PANELS_INITIAL = [
  { panelIndex: 1, visualDescription: "Weary watchmaker wiping grease-stained hands under rain-slicked alley lights.", camera: "Medium Shot", speech: "Sector 4 rain never stops...", caption: "" },
  { panelIndex: 2, visualDescription: "Extreme close-up of a brass dial with glowing amber runes humming in a dark hand.", camera: "Extreme Close-Up", speech: "", caption: "Its ancient runes hummed with stolen time." },
  { panelIndex: 3, visualDescription: "Shadowy cloaked figures of the Watchmaker Guild emerging from the mist.", camera: "Low Angle", speech: "Surrender the artifact!", caption: "" },
  { panelIndex: 4, visualDescription: "Kaelen sprinting down a neon-lit alley, coat flaring behind him.", camera: "Wide Shot", speech: "Not today.", caption: "" },
];

const TIMELINE_NODES = [
  { id: "t1", title: "Chap 1: The First Flip", status: "PUBLISHED", exported: true },
  { id: "t2", title: "Chap 2: Catacomb Descent", status: "PUBLISHED", exported: true },
  { id: "t3", title: "Chap 3", status: "DRAFT", exported: false },
];
const TIMELINE_BRANCH = { id: "t2b", title: "Chap 2 (Alt): Upper Tower", status: "BRANCH_OPTION", exported: false };

const SANDBOX_ROSTER_INITIAL = [
  { id: "s1", name: "Kael", role: "Protagonist", status: "ACTIVE", location: "Cloud City", avatar: false, locked: true },
  { id: "s2", name: "Lyra", role: "Mechanic", status: "ACTIVE", location: "Cloud City", avatar: false, locked: true },
  { id: "s3", name: "Vance", role: "Founder", status: "DECEASED", location: "Unknown", avatar: false, locked: true },
  { id: "s4", name: "YOU", role: "Self-Avatar", status: "ACTIVE", location: "Main Citadel", avatar: true, locked: false },
];

const REALMS = ["Upper Citadel", "Lower Catacombs", "Cloud City", "Main Citadel"];

const ARC_OPTIONS = [
  { id: "opt_1", title: "The Ancient Core", summary: "An ancient power core awakens in the Lower Catacombs. The squad must secure it before Founder Vance's AI defense grid reaches full operational capacity.", objectives: ["Uncover Catacomb Secrets", "Disable Vance's AI"] },
  { id: "opt_2", title: "Shadow Infiltration", summary: "Vance's automated defense units have trapped the group inside the lower grid. A rogue faction offers an escape route at a heavy price.", objectives: ["Escape Automated Trap", "Negotiate with Rogue Faction"] },
  { id: "opt_3", title: "The Anomaly Shift", summary: "A sudden dimensional tear opens in the catacombs, altering the behavior of surviving entities and revealing hidden realm pathways.", objectives: ["Investigate Tear Source", "Seal Spatial Anomaly"] },
];

/* ---------------------------------------------------------------------- */
/* Cast setup — predefined characters, editable only pre-launch            */
/* ---------------------------------------------------------------------- */

const CAST_INITIAL = [
  {
    id: "cast_1", name: "Kaelen", role: "Protagonist · Rogue Watchmaker",
    voice: "Terse, dry humor masking exhaustion",
    traits: "Cautious, methodical, fiercely loyal",
    visual: "Grease-stained hands, long coat, tired eyes",
    hidden: "Sabotaged the Spire's original clock mechanism years ago — the failure everyone blames on Vance was his.",
  },
  {
    id: "cast_2", name: "Mira Voss", role: "Guild Enforcer · Antagonist",
    voice: "Clipped, procedural, quietly menacing",
    traits: "Rule-bound, relentless, secretly conflicted",
    visual: "Ticking brass mask, charcoal cloak",
    hidden: "Is Vance's estranged daughter and has known Kaelen's face since childhood.",
  },
  {
    id: "cast_3", name: "Dial of Anos", role: "Sentient Artifact · Companion",
    voice: "Ancient, layered echo, speaks in fragments",
    traits: "Patient, cryptic, protective of Kaelen",
    visual: "Glowing amber runes, dark matte steel",
    hidden: "Is slowly rewriting Kaelen's memories to erase what he did to the original mechanism.",
  },
];

/* Story output — scenes with per-character screenplay dialogue            */

const SCENES_CH1 = [
  {
    slugline: "INT. SECTOR 4 — ALLEYWAY — NIGHT",
    action: "Rain streaks a filthy window. KAELEN wipes grease-stained hands on a rag gone permanently grey, watching the drips race each other down the glass.",
    dialogue: [
      { character: "KAELEN", parenthetical: "to himself", line: "Sector 4 rain never stops. Guess neither do I." },
    ],
  },
  {
    slugline: "INT. SECTOR 4 — ALLEYWAY — CONTINUOUS",
    action: "The DIAL OF ANOS hums against his ribs, a rhythm older than his own pulse — slower, patient in a way nothing in Sector 4 has any right to be.",
    dialogue: [
      { character: "DIAL OF ANOS", parenthetical: "V.O. · fragmented", line: "...hours... counted... not yours to keep..." },
      { character: "KAELEN", line: "Keep talking like that and I'll pawn you for scrap." },
    ],
  },
  {
    slugline: "EXT. CHRONO-SPIRE — UPPER RING — NIGHT",
    action: "Cloaked GUILD OVERSEERS spill from the mist, brass masks ticking in unison.",
    dialogue: [
      { character: "MIRA VOSS", parenthetical: "commanding", line: "Surrender the artifact, Watchmaker. This corridor is already ours." },
    ],
  },
];

const SCENES_CH2 = [
  {
    slugline: "EXT. SECTOR 4 — BACK ALLEY — CONTINUOUS",
    action: "The alley swallows KAELEN whole, neon smearing into streaks as the Dial's hum climbs to a fever pitch against his ribs.",
    dialogue: [
      { character: "KAELEN", parenthetical: "breathless", line: "You could've picked a quieter host, you know." },
      { character: "DIAL OF ANOS", parenthetical: "V.O.", line: "...quiet ones... don't survive..." },
    ],
  },
  {
    slugline: "EXT. SECTOR 7 THRESHOLD — MOMENTS LATER",
    action: "Behind him, MIRA VOSS and the masked overseers move like they have all the time in the world — because, Kaelen realizes, they do.",
    dialogue: [
      { character: "MIRA VOSS", parenthetical: "distant, unhurried", line: "Running changes nothing. We count faster than you can run." },
    ],
  },
];

const CHOICE_LOG_INITIAL = [
  { chapter: 1, said: "Story launched from the Chrono-Shards of Neon concept — no prior input yet." },
];

/* ---------------------------------------------------------------------- */
/* Evaluator agent — character & world consistency check                  */
/* ---------------------------------------------------------------------- */

const EVALUATOR_REPORT = {
  overallStatus: "MINOR_DIVERGENCE",
  characters: [
    { name: "Kaelen", status: "IN_SYNC", note: "Consistent with the established caution, dry humor, and grease-stained motif set at cast lock across Chapters 1–2." },
    { name: "Mira Voss", status: "DIVERGENCE", note: "Locked as rule-bound and procedural — Chapter 2's line reads more casual and taunting than the baseline voice. Flagged for review." },
    { name: "Dial of Anos", status: "IN_SYNC", note: "Fragmented, ancient cadence holds steady across every appearance so far." },
  ],
  worldFacts: [
    { label: "Sector 4 rain / ozone motif", status: "IN_SYNC" },
    { label: "Guild masks always ticking", status: "IN_SYNC" },
    { label: "Dial's rune color (amber, not blue)", status: "IN_SYNC" },
  ],
};

/* ---------------------------------------------------------------------- */
/* Business agent — is the story looking interesting?                     */
/* ---------------------------------------------------------------------- */

const BUSINESS_REPORT = {
  score: 78,
  verdict: "Strong hook, pacing dips mid-arc",
  breakdown: [
    { label: "Hook strength (Ch1)", score: 92 },
    { label: "Pacing", score: 68 },
    { label: "Stakes clarity", score: 81 },
    { label: "Character likability", score: 74 },
  ],
  note: "Chapter 1 lands a strong hook — the ticking-clock artifact premise tests well. Chapter 2's chase sequence sags a little; tightening it would help retention. The genre mashup (cyberpunk + clockwork fantasy) is distinctive but skews niche for a first issue.",
};

/* ---------------------------------------------------------------------- */
/* Small shared components                                                 */
/* ---------------------------------------------------------------------- */

function DialLogo() {
  return (
    <svg className="se-dial" viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="17" stroke="#E8A33D" strokeWidth="1.4" opacity="0.9" />
      <circle cx="20" cy="20" r="11" stroke="#8C6BFF" strokeWidth="1" opacity="0.6" />
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i / 12) * Math.PI * 2;
        const x1 = 20 + Math.cos(a) * 15, y1 = 20 + Math.sin(a) * 15;
        const x2 = 20 + Math.cos(a) * 17.5, y2 = 20 + Math.sin(a) * 17.5;
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#E8A33D" strokeWidth="1" opacity="0.7" />;
      })}
      <circle cx="20" cy="20" r="2.5" fill="#E8A33D" />
    </svg>
  );
}

function Badge({ status }) {
  const map = {
    ACTIVE: "se-badge-active", DECEASED: "se-badge-deceased", EXILED: "se-badge-exiled",
    DRAFT: "se-badge-draft", PUBLISHED: "se-badge-published", BRANCH_OPTION: "se-badge-draft",
  };
  return <span className={`se-badge ${map[status] || "se-badge-active"}`}>{status.replace("_", " ")}</span>;
}

function LoadingLine({ text }) {
  return (
    <div className="se-loading">
      <RefreshCw size={13} className="se-spin" />
      {text}
    </div>
  );
}

function LockPill({ isNew }) {
  return isNew ? (
    <span className="se-lock-pill new"><Sparkle size={10} /> Introduced mid-story</span>
  ) : (
    <span className="se-lock-pill"><Lock size={10} /> Locked at start</span>
  );
}

function SyncBadge({ status }) {
  if (status === "IN_SYNC") {
    return <span className="se-badge se-badge-active"><ShieldCheck size={11} /> In sync</span>;
  }
  return <span className="se-badge se-badge-deceased"><ShieldAlert size={11} /> Divergence</span>;
}

function ScoreBar({ label, score }) {
  return (
    <div className="se-score-bar-row">
      <span className="se-score-bar-label">{label}</span>
      <div className="se-score-bar-track">
        <div className="se-score-bar-fill" style={{ width: `${score}%` }} />
      </div>
      <span className="se-score-bar-val">{score}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 1 — Seeding                                                      */
/* ---------------------------------------------------------------------- */

const SEED_TYPES = [
  { key: "CUSTOM", icon: Edit3, title: "Custom Prompt", desc: "Start from your own idea, written out." },
  { key: "DREAM_FRAGMENT", icon: Sparkle, title: "Dream Fragment", desc: "A hazy scene or image you remember." },
  { key: "PARTIAL_STORY", icon: BookOpen, title: "Partial Narrative", desc: "You've already got a scene or two." },
  { key: "PRESET", icon: Layers, title: "Preset Story", desc: "Pick a ready-made starter world." },
];

const ALL_GENRES = ["Sci-Fi", "Cyberpunk", "High Fantasy", "Mystery", "Horror", "Romance"];
const ALL_TONES = ["Epic / Heroic", "Dark & Gritty", "Humorous", "Whimsical", "Melancholic"];

function Screen1({ goTo }) {
  const [step, setStep] = useState(0);
  const [seedType, setSeedType] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [genres, setGenres] = useState([]);
  const [tone, setTone] = useState(null);
  const [artStyle, setArtStyle] = useState("Cyberpunk Anime");
  const [loading, setLoading] = useState(false);

  const totalSteps = 4;

  const toggleGenre = (g) =>
    setGenres((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]));

  const canAdvance = [
    !!seedType,
    prompt.trim().length >= 20,
    genres.length > 0 && !!tone,
    true,
  ][step];

  const pickSeedType = (key) => {
    setSeedType(key);
    // Only requires a click to choose — jump straight to the next question.
    setStep(1);
  };

  const fillExample = () => {
    setSeedType("CUSTOM");
    setPrompt("A world where time is stored in glowing crystals. A rogue watchmaker discovers an illegal artifact that speaks in ancient dialects.");
    setGenres(["Sci-Fi", "Cyberpunk", "Mystery"]);
    setTone("Dark & Gritty");
    setStep(3);
  };

  const generate = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); goTo("concepts"); }, 900);
  };

  const next = () => setStep((s) => Math.min(s + 1, totalSteps - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div className="se-wizard">
      <div className="se-eyebrow">Screen 01 · Story Seeding</div>
      <h1 className="se-h1" style={{ fontSize: 26, marginBottom: 4 }}>Plant the first spark</h1>
      <p className="se-sub" style={{ marginBottom: 24, fontSize: 13 }}>
        Four quick questions, one at a time — then we'll draft three story directions.{" "}
        <button className="se-skip-link" onClick={fillExample}>Or try an example</button>
      </p>

      <div className="se-wizard-progress">
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div key={i} className={`se-wizard-dot ${i < step ? "done" : i === step ? "current" : ""}`} />
        ))}
      </div>

      <div className="se-wizard-body">
        {step === 0 && (
          <div>
            <div className="se-wizard-stepnum">Question 1 of 4</div>
            <div className="se-wizard-q">Where does this story start?</div>
            <p className="se-wizard-hint">Pick whichever matches what you're bringing to the table.</p>
            <div className="se-option-grid">
              {SEED_TYPES.map((s) => (
                <button key={s.key} className={`se-option-card ${seedType === s.key ? "selected" : ""}`} onClick={() => pickSeedType(s.key)}>
                  <div className="se-option-icon"><s.icon size={16} /></div>
                  <div className="se-option-title">{s.title}</div>
                  <div className="se-option-desc">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <div className="se-wizard-stepnum">Question 2 of 4</div>
            <div className="se-wizard-q">What's the idea?</div>
            <p className="se-wizard-hint">A sentence or two is plenty — the engine builds it out from here.</p>
            <textarea
              autoFocus
              className="se-wizard-textarea"
              placeholder="A world where time is stored in glowing crystals…"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value.slice(0, 2000))}
            />
            <div className="se-charcount" style={{ marginTop: 8 }}>{prompt.length} / 2000 · minimum 20 characters</div>
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="se-wizard-stepnum">Question 3 of 4</div>
            <div className="se-wizard-q">What's the mood?</div>
            <p className="se-wizard-hint">Pick one or more genres and a tone that fits.</p>
            <div className="se-tag-cluster">
              <div className="se-tag-cluster-label">Genre</div>
              <div className="se-pill-grid" style={{ marginBottom: 0 }}>
                {ALL_GENRES.map((g) => (
                  <button key={g} className={`se-pill ${genres.includes(g) ? "active" : ""}`} onClick={() => toggleGenre(g)}>{g}</button>
                ))}
              </div>
            </div>
            <div className="se-tag-cluster" style={{ marginBottom: 0 }}>
              <div className="se-tag-cluster-label">Tone</div>
              <div className="se-radio-row" style={{ marginBottom: 0 }}>
                {ALL_TONES.map((t) => (
                  <button key={t} className={`se-radio ${tone === t ? "active" : ""}`} onClick={() => setTone(t)}>
                    <span className="se-dot" />{t}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <div className="se-wizard-stepnum">Question 4 of 4</div>
            <div className="se-wizard-q">Quick look before we generate</div>
            <p className="se-wizard-hint">Everything here is editable later — this is just a gut check.</p>

            <div className="se-card" style={{ marginBottom: 18 }}>
              <div className="se-review-row">
                <span className="se-review-key">Seed type</span>
                <span className="se-review-val">{SEED_TYPES.find((s) => s.key === seedType)?.title || "—"}</span>
              </div>
              <div className="se-review-row">
                <span className="se-review-key">Idea</span>
                <span className="se-review-val">{prompt || "—"}</span>
              </div>
              <div className="se-review-row">
                <span className="se-review-key">Genre</span>
                <span className="se-review-val">{genres.join(", ") || "—"}</span>
              </div>
              <div className="se-review-row">
                <span className="se-review-key">Tone</span>
                <span className="se-review-val">{tone || "—"}</span>
              </div>
              <div className="se-review-row">
                <span className="se-review-key">Style</span>
                <span className="se-review-val">
                  <select className="se-select" value={artStyle} onChange={(e) => setArtStyle(e.target.value)}>
                    <option>Cyberpunk Anime</option>
                    <option>Ink &amp; Watercolor</option>
                    <option>Painterly Realism</option>
                  </select>
                </span>
              </div>
            </div>

            {loading ? (
              <LoadingLine text="Drafting three concepts…" />
            ) : (
              <button className="se-btn se-btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={generate}>
                <Wand2 size={15} /> Generate story concepts
              </button>
            )}
          </div>
        )}
      </div>

      {step < 3 && (
        <div className="se-wizard-nav">
          <button className="se-btn se-btn-ghost" onClick={back} disabled={step === 0} style={{ visibility: step === 0 ? "hidden" : "visible" }}>
            ← Back
          </button>
          <button className="se-btn se-btn-primary" onClick={next} disabled={!canAdvance}>
            Next <ChevronRight size={15} />
          </button>
        </div>
      )}
      {step === 3 && (
        <div className="se-wizard-nav" style={{ justifyContent: "flex-start", marginTop: 14 }}>
          <button className="se-btn se-btn-ghost" onClick={back}>← Back</button>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 2 — Concept selection                                            */
/* ---------------------------------------------------------------------- */

function Screen2({ goTo }) {
  const [selected, setSelected] = useState("concept_1");
  const [editing, setEditing] = useState(null);
  const [concepts, setConcepts] = useState(CONCEPTS);
  const [loading, setLoading] = useState(false);

  const updateField = (id, field, value) =>
    setConcepts((prev) => prev.map((c) => (c.id === id ? { ...c, [field]: value } : c)));

  const regenerate = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 900);
  };

  const launch = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); goTo("characters"); }, 900);
  };

  return (
    <div>
      <div className="se-eyebrow">Screen 02 · Concept Selection</div>
      <h1 className="se-h1">Select your story arc</h1>
      <p className="se-sub">Review the three generated directions. Edit any detail inline before you initialize the universe.</p>

      <div className="se-concept-grid">
        {concepts.map((c) => (
          <div key={c.id} className={`se-concept-card ${selected === c.id ? "selected" : ""}`} onClick={() => setSelected(c.id)}>
            <div className="se-flex-between">
              <span className="se-eyebrow" style={{ marginBottom: 0 }}>{c.id === selected ? "Selected" : "Concept"}</span>
              {selected === c.id && <Check size={16} color="var(--amber)" />}
            </div>
            {editing === c.id ? (
              <input className="se-input se-textarea" style={{ minHeight: "auto", fontFamily: "Fraunces, serif", fontSize: 17, fontWeight: 600 }}
                value={c.title} onChange={(e) => updateField(c.id, "title", e.target.value)} onClick={(e) => e.stopPropagation()} />
            ) : (
              <h3 className="se-concept-title">{c.title}</h3>
            )}
            <div className="se-concept-tag">"{c.tagline}"</div>
            {editing === c.id ? (
              <textarea className="se-textarea" style={{ minHeight: 70, fontSize: 12.5 }}
                value={c.summary} onChange={(e) => updateField(c.id, "summary", e.target.value)} onClick={(e) => e.stopPropagation()} />
            ) : (
              <p className="se-concept-summary">{c.summary}</p>
            )}
            <div className="se-concept-conflict-label">Core conflict</div>
            <p className="se-concept-summary" style={{ marginTop: -6 }}>{c.coreConflict}</p>
            <div className="se-concept-conflict-label">Initial entities</div>
            <div>
              {c.entities.map((e) => (
                <span key={e.name} className="se-entity-chip">{e.name} · {e.type}</span>
              ))}
            </div>
            <button
              className="se-btn se-btn-ghost se-btn-sm"
              style={{ alignSelf: "flex-start", marginTop: 4 }}
              onClick={(e) => { e.stopPropagation(); setEditing(editing === c.id ? null : c.id); }}
            >
              <Edit3 size={12} /> {editing === c.id ? "Done editing" : "Edit concept inline"}
            </button>
          </div>
        ))}
      </div>

      <div className="se-flex-between">
        {loading ? (
          <LoadingLine text="Working…" />
        ) : (
          <button className="se-btn se-btn-ghost" onClick={regenerate}>
            <RefreshCw size={14} /> Regenerate all concepts
          </button>
        )}
        {!loading && (
          <button className="se-btn se-btn-primary" onClick={launch}>
            <Zap size={15} /> Continue to cast setup
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 2B — Character cast setup (editable only before launch)          */
/* ---------------------------------------------------------------------- */

function ScreenCharacters({ goTo }) {
  const [cast, setCast] = useState(CAST_INITIAL);
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(false);
  // In production this reads the genre(s) chosen on the concept screen —
  // hard-coded here since this prototype doesn't thread state across screens.
  // Default preset genres include "Mystery", so the detective hidden-trait
  // feature is on for this cast.
  const isDetectiveGenre = true;

  const updateField = (id, field, value) =>
    setCast((prev) => prev.map((c) => (c.id === id ? { ...c, [field]: value } : c)));

  const removeChar = (id) => setCast((prev) => prev.filter((c) => c.id !== id));

  const addChar = () => {
    const n = cast.length + 1;
    setCast((prev) => [
      ...prev,
      { id: `cast_new_${Date.now()}`, name: `New Character ${n}`, role: "Supporting", voice: "", traits: "", visual: "" },
    ]);
  };

  const confirmCast = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); setLocked(true); }, 800);
  };

  return (
    <div>
      <div className="se-eyebrow">Screen 03 · Cast &amp; Characters</div>
      <h1 className="se-h1">Define your starting cast</h1>
      <p className="se-sub">
        Set names, voice, and traits for every character now — once you lock the cast, these predefined
        characters can't be edited mid-story. You can still introduce brand-new characters as the story unfolds.
      </p>

      <div className="se-cast-grid">
        {cast.map((c) => (
          <div key={c.id} className={`se-cast-card ${locked ? "locked" : ""}`}>
            <div className="se-cast-head">
              {locked ? (
                <span className="se-concept-title" style={{ fontSize: 15 }}>{c.name}</span>
              ) : (
                <input className="se-cast-input" style={{ fontFamily: "Fraunces, serif", fontSize: 15, fontWeight: 600 }}
                  value={c.name} onChange={(e) => updateField(c.id, "name", e.target.value)} />
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <LockPill isNew={c.id.startsWith("cast_new_")} />
                {!locked && cast.length > 1 && (
                  <button className="se-btn se-btn-ghost se-btn-sm" style={{ padding: 6 }} onClick={() => removeChar(c.id)}><Trash2 size={11} /></button>
                )}
              </div>
            </div>

            <div className="se-cast-field-label">Role</div>
            {locked ? <p className="se-concept-summary" style={{ margin: 0 }}>{c.role}</p> :
              <input className="se-cast-input" value={c.role} onChange={(e) => updateField(c.id, "role", e.target.value)} />}

            <div className="se-cast-field-label">Voice / dialogue style</div>
            {locked ? <p className="se-concept-summary" style={{ margin: 0 }}>{c.voice || "—"}</p> :
              <input className="se-cast-input" value={c.voice} onChange={(e) => updateField(c.id, "voice", e.target.value)} placeholder="e.g. Terse, dry humor" />}

            <div className="se-cast-field-label">Core traits</div>
            {locked ? <p className="se-concept-summary" style={{ margin: 0 }}>{c.traits || "—"}</p> :
              <input className="se-cast-input" value={c.traits} onChange={(e) => updateField(c.id, "traits", e.target.value)} placeholder="e.g. Cautious, loyal" />}

            <div className="se-cast-field-label">Visual attributes</div>
            {locked ? <p className="se-concept-summary" style={{ margin: 0 }}>{c.visual || "—"}</p> :
              <input className="se-cast-input" value={c.visual} onChange={(e) => updateField(c.id, "visual", e.target.value)} placeholder="e.g. Long coat, tired eyes" />}

            {isDetectiveGenre && (
              <div className="se-hidden-row">
                <div className="se-hidden-label"><Lock size={10} /> Hidden characteristic</div>
                <p className="se-hidden-line">{c.hidden || "A secret has been generated for this character."}</p>
                <p className="se-hidden-note">Concealed from view — may surface as a twist as the story unfolds.</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {!locked && (
        <button className="se-btn se-btn-ghost" style={{ marginBottom: 22 }} onClick={addChar}>
          <UserPlus size={14} /> Add another starting character
        </button>
      )}

      <div className="se-flex-between">
        <button className="se-btn se-btn-ghost" onClick={() => goTo("concepts")}>← Back to concept</button>
        {locked ? (
          <button className="se-btn se-btn-primary" onClick={() => goTo("workspace")}>
            <BookOpen size={15} /> Enter narrative workspace
          </button>
        ) : loading ? (
          <LoadingLine text="Locking cast…" />
        ) : (
          <button className="se-btn se-btn-primary" onClick={confirmCast}>
            <Lock size={15} /> Lock cast &amp; launch Chapter 1
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 3 — Workspace: entity graph + reader                             */
/* ---------------------------------------------------------------------- */

function EntityGraph({ entities, relationships, onSelect, selectedId }) {
  const posOf = (id) => entities.find((e) => e.id === id);
  return (
    <div className="se-graph-panel">
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {relationships.map((r, i) => {
          const a = posOf(r.from), b = posOf(r.to);
          if (!a || !b) return null;
          const x1 = a.x + 74, y1 = a.y + 24, x2 = b.x + 74, y2 = b.y + 24;
          const midX = (x1 + x2) / 2, midY = (y1 + y2) / 2;
          return (
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#3A4370" strokeWidth="1.4" strokeDasharray="4 4" />
              <rect x={midX - 38} y={midY - 9} width="76" height="16" rx="4" fill="#12172A" stroke="#2A3255" />
              <text x={midX} y={midY + 3} textAnchor="middle" fontSize="8.5" fill="#9AA1C2" fontFamily="IBM Plex Mono, monospace">{r.label}</text>
            </g>
          );
        })}
      </svg>
      {entities.map((e) => (
        <div
          key={e.id}
          className={`se-node ${e.status === "ACTIVE" && selectedId === e.id ? "active-glow" : ""} ${e.status === "DECEASED" ? "deceased" : ""}`}
          style={{ left: e.x, top: e.y }}
          onClick={() => onSelect(e)}
        >
          <div className="se-flex-between" style={{ marginBottom: 2 }}>
            <div className="se-node-name">{e.name}</div>
            {e.type === "HUMANOID" && (e.locked ? <Lock size={10} color="var(--ink-faint)" /> : <Sparkle size={10} color="var(--teal)" />)}
          </div>
          <div className="se-node-role">{e.role}</div>
        </div>
      ))}
      <div style={{ position: "absolute", bottom: 12, left: 12, display: "flex", gap: 6 }}>
        {["+", "–", "Fit"].map((z) => (
          <span key={z} className="se-btn se-btn-ghost se-btn-sm" style={{ padding: "5px 10px" }}>{z}</span>
        ))}
      </div>
    </div>
  );
}

function Screen3({ goTo }) {
  const [entities, setEntities] = useState(
    ENTITIES.map((e) => ({ ...e, locked: e.type === "HUMANOID" }))
  );
  const [selectedEntity, setSelectedEntity] = useState(entities[0]);
  const [chapterNum, setChapterNum] = useState(1);
  const [scenes, setScenes] = useState(SCENES_CH1);
  const [choiceLog, setChoiceLog] = useState(CHOICE_LOG_INITIAL);
  const [editingText, setEditingText] = useState(false);
  const [choiceId, setChoiceId] = useState(null);
  const [customChoice, setCustomChoice] = useState("");
  const [loading, setLoading] = useState(false);

  const introduceCharacter = () => {
    const n = entities.filter((e) => e.type === "HUMANOID").length + 1;
    const id = `e_new_${Date.now()}`;
    const newChar = {
      id, name: `New Character ${n}`, role: "Introduced mid-story", type: "HUMANOID", status: "ACTIVE",
      location: "Sector 4", x: 180, y: 145, visual: "Not yet defined", locked: false,
    };
    setEntities((prev) => [...prev, newChar]);
    setSelectedEntity(newChar);
  };

  const progress = () => {
    const chosenText = choiceId === "custom" ? customChoice : CHOICES.find((c) => c.id === choiceId)?.text;
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setChoiceLog((prev) => [...prev, { chapter: chapterNum, said: chosenText || "(no action recorded)" }]);
      setChapterNum((n) => n + 1);
      setScenes(SCENES_CH2);
      setChoiceId(null);
      setCustomChoice("");
    }, 1000);
  };

  return (
    <div>
      <div className="se-topbar">
        <div className="se-topbar-left">
          <span className="se-topbar-title">Chrono-Shards of Neon</span>
          <span>Chapter {chapterNum} of 5</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="se-agent-topchip" onClick={() => goTo("agents")}><ShieldCheck size={12} color="var(--teal)" /> Sync: 2/3</button>
          <button className="se-agent-topchip" onClick={() => goTo("agents")}><TrendingUp size={12} color="var(--amber)" /> Interest: 78</button>
          <button className="se-btn se-btn-violet se-btn-sm" onClick={() => goTo("comic")}>
            <ImageIcon size={13} /> Open Comic Studio
          </button>
        </div>
      </div>

      <div className="se-split">
        <div>
          <div className="se-flex-between" style={{ marginBottom: 12 }}>
            <div className="se-section-label" style={{ marginBottom: 0 }}><GitBranch size={13} /> Dynamic entity graph</div>
            <button className="se-btn se-btn-violet se-btn-sm" onClick={introduceCharacter}><UserPlus size={12} /> Introduce new character</button>
          </div>
          <EntityGraph entities={entities} relationships={RELATIONSHIPS} onSelect={setSelectedEntity} selectedId={selectedEntity?.id} />
          {selectedEntity && (
            <div className="se-card se-mt">
              <div className="se-flex-between" style={{ marginBottom: 8 }}>
                <span className="se-concept-title" style={{ fontSize: 15 }}>{selectedEntity.name}</span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {selectedEntity.type === "HUMANOID" && <LockPill isNew={!selectedEntity.locked} />}
                  <Badge status={selectedEntity.status} />
                </div>
              </div>
              <div className="se-concept-summary">
                <strong style={{ color: "var(--ink-dim)" }}>Location:</strong> {selectedEntity.location}<br />
                <strong style={{ color: "var(--ink-dim)" }}>Visual attributes:</strong> {selectedEntity.visual}
              </div>
              {selectedEntity.type === "HUMANOID" && selectedEntity.locked && (
                <p className="se-charcount" style={{ marginTop: 8 }}>Core identity was set during cast setup and can't be changed mid-story.</p>
              )}
            </div>
          )}
        </div>

        <div className="se-reader-panel">
          <div className="se-eyebrow">Chapter {chapterNum}</div>
          <div className="se-reader-title">{chapterNum === 1 ? "The First Clockwork Dial" : "Sector 7 Threshold"}</div>

          {choiceLog.length > 0 && (
            <div className="se-choicelog">
              <div className="se-eyebrow" style={{ marginBottom: 6 }}><MessageSquare size={12} /> Your input so far</div>
              {choiceLog.map((c, i) => (
                <div key={i} className="se-choicelog-item">
                  <span className="se-choicelog-chap">Ch.{c.chapter}</span>
                  <span>{c.said}</span>
                </div>
              ))}
            </div>
          )}

          {editingText ? (
            <textarea
              className="se-reader-textarea"
              value={scenes.map((s) => `${s.slugline}\n${s.action}\n${s.dialogue.map((d) => `${d.character}: ${d.line}`).join("\n")}`).join("\n\n")}
              onChange={() => {}}
              readOnly
            />
          ) : (
            <div>
              <div className="se-eyebrow" style={{ marginBottom: 8 }}><Clapperboard size={12} /> Screenplay</div>
              {scenes.map((s, i) => (
                <div key={i}>
                  <div className="se-slugline">{s.slugline}</div>
                  <p className="se-scene-action">{s.action}</p>
                  {s.dialogue.map((d, j) => (
                    <div key={j} className="se-dialogue-block">
                      <div className="se-dialogue-character">{d.character}</div>
                      {d.parenthetical && <div className="se-dialogue-paren">({d.parenthetical})</div>}
                      <div className="se-dialogue-line">{d.line}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
          <button className="se-btn se-btn-ghost se-btn-sm" style={{ borderColor: "#D9CDA9", color: "#8A6E2E", marginTop: 6 }} onClick={() => setEditingText((v) => !v)}>
            <Edit3 size={12} /> {editingText ? "Done editing" : "View raw script text"}
          </button>

          <div style={{ borderTop: "1px solid #D9CDA9", margin: "20px 0 14px" }} />
          <div className="se-eyebrow">Branching decision</div>
          {CHOICES.map((c) => (
            <div key={c.id} className={`se-choice ${choiceId === c.id ? "selected" : ""}`} onClick={() => setChoiceId(c.id)}>
              <span className={`se-choice-radio ${choiceId === c.id ? "on" : ""}`} />
              {c.text}
            </div>
          ))}
          <div className={`se-choice ${choiceId === "custom" ? "selected" : ""}`} onClick={() => setChoiceId("custom")}>
            <span className={`se-choice-radio ${choiceId === "custom" ? "on" : ""}`} />
            <input className="se-choice-input" placeholder="Type your own action…" value={customChoice}
              onChange={(e) => { setCustomChoice(e.target.value); setChoiceId("custom"); }} />
          </div>

          <div style={{ marginTop: 16, textAlign: "right" }}>
            {loading ? (
              <span style={{ color: "#8A6E2E" }}><LoadingLine text="Writing next chapter…" /></span>
            ) : (
              <button className="se-btn se-btn-primary" disabled={!choiceId} onClick={progress}>
                Progress to Chapter {chapterNum + 1} <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 4 — Comic studio                                                 */
/* ---------------------------------------------------------------------- */

function Screen4({ goTo }) {
  const [layout, setLayout] = useState("4-Panel Grid (2x2)");
  const [panels, setPanels] = useState(PANELS_INITIAL);
  const [regenIndex, setRegenIndex] = useState(null);

  const regen = (idx) => {
    setRegenIndex(idx);
    setTimeout(() => setRegenIndex(null), 800);
  };

  const updateSpeech = (idx, val) =>
    setPanels((prev) => prev.map((p, i) => (i === idx ? { ...p, speech: val } : p)));

  return (
    <div>
      <div className="se-topbar">
        <div className="se-topbar-left">
          <button className="se-btn se-btn-ghost se-btn-sm" onClick={() => goTo("workspace")}>← Back to chapter</button>
          <span className="se-topbar-title">Chapter 1 Comic Layout</span>
        </div>
        <button className="se-btn se-btn-primary se-btn-sm"><Download size={13} /> Export PDF / PNG</button>
      </div>

      <div className="se-section-label"><LayoutGrid size={13} /> Layout preset</div>
      <div className="se-radio-row">
        {["4-Panel Grid (2x2)", "6-Panel Action Page", "Manga Style Vertical", "Splash Panel"].map((l) => (
          <button key={l} className={`se-radio ${layout === l ? "active" : ""}`} onClick={() => setLayout(l)}>
            <span className="se-dot" />{l}
          </button>
        ))}
      </div>

      <div className="se-comic-grid">
        {panels.map((p, i) => (
          <div key={i} className="se-panel-card">
            <div className="se-panel-art" style={{ background: PANEL_ART[i % PANEL_ART.length] }}>
              {regenIndex === i ? (
                <span className="se-loading" style={{ color: "white" }}><RefreshCw size={13} className="se-spin" /> Regenerating…</span>
              ) : (
                <span className="se-mono" style={{ fontSize: 10.5, opacity: 0.85 }}>{p.camera}</span>
              )}
            </div>
            <div className="se-panel-body">
              <div className="se-flex-between">
                <span className="se-concept-conflict-label">Panel {p.panelIndex}</span>
                <button className="se-btn se-btn-ghost se-btn-sm" onClick={() => regen(i)}><RefreshCw size={11} /> Regenerate</button>
              </div>
              <p className="se-concept-summary" style={{ marginTop: 6 }}>{p.visualDescription}</p>
              {p.speech && <div className="se-panel-speech">"{p.speech}"</div>}
              {p.caption && <div className="se-panel-caption" style={{ marginTop: 6 }}>{p.caption}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="se-card se-mt">
        <div className="se-section-label"><Edit3 size={13} /> Edit panel dialogue &amp; captions</div>
        {panels.filter((p) => p.speech).map((p, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <label className="se-charcount">Panel {p.panelIndex} text</label>
            <input className="se-textarea" style={{ minHeight: "auto", padding: "10px 14px" }} value={p.speech}
              onChange={(e) => updateSpeech(panels.indexOf(p), e.target.value)} />
          </div>
        ))}
        <div style={{ textAlign: "right", marginTop: 12 }}>
          <button className="se-btn se-btn-primary"><Film size={15} /> Export full comic book (PDF)</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 5 — Progression & volume manager                                 */
/* ---------------------------------------------------------------------- */

function Screen5({ goTo }) {
  return (
    <div>
      <div className="se-eyebrow">Screen 06 · Progression &amp; Volume Manager</div>
      <h1 className="se-h1">Neon Gravity — story control room</h1>
      <p className="se-sub">Track every branch of the timeline, preview the compiled comic volume, and decide what happens next.</p>

      <div className="se-card">
        <div className="se-section-label"><GitBranch size={13} /> Story branch timeline</div>
        <div className="se-timeline-track">
          {TIMELINE_NODES.map((n, i) => (
            <div key={n.id} className="se-tl-node">
              <div className="se-tl-title">{n.title}</div>
              <Badge status={n.status} />
              {n.exported && <div className="se-charcount" style={{ marginTop: 8, color: "var(--teal)" }}>✓ Comic exported</div>}
              {i < TIMELINE_NODES.length - 1 && <span className="se-tl-arrow">→</span>}
              {i === 1 && (
                <div className="se-tl-node branch" style={{ position: "absolute", top: 92, left: 0 }}>
                  <div className="se-tl-title">{TIMELINE_BRANCH.title}</div>
                  <Badge status={TIMELINE_BRANCH.status} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="se-two-col se-mt">
        <div className="se-card">
          <div className="se-section-label"><BookOpen size={13} /> Comic volume preview</div>
          <div style={{ height: 150, borderRadius: 10, background: "linear-gradient(135deg, #2A2140, #C4633B)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
            <div style={{ textAlign: "center" }}>
              <div className="se-mono" style={{ fontSize: 10, letterSpacing: "0.1em", opacity: 0.8 }}>ISSUE #1</div>
              <div className="se-serif" style={{ fontSize: 20, fontWeight: 700 }}>NEON GRAVITY</div>
            </div>
          </div>
          <div className="se-concept-summary">Pages generated: 8 panels across 2 chapters</div>
          <button className="se-btn se-btn-ghost se-mt" style={{ width: "100%", justifyContent: "center" }}>
            <Download size={14} /> Download full issue PDF
          </button>
        </div>

        <div className="se-card">
          <div className="se-section-label"><Zap size={13} /> Next action</div>
          <p className="se-concept-summary" style={{ marginBottom: 16 }}>Ready to write or generate the next issue?</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <button className="se-btn se-btn-ghost" onClick={() => goTo("workspace")}><BookOpen size={14} /> Continue narrative reader</button>
            <button className="se-btn se-btn-violet"><Wand2 size={14} /> Auto-draft Chapter 3 narrative</button>
            <button className="se-btn se-btn-ghost" onClick={() => goTo("sandbox")}><GitBranch size={14} /> Branch off alternate story path</button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 6 — World control sandbox                                        */
/* ---------------------------------------------------------------------- */

function Screen6({ goTo }) {
  const [roster, setRoster] = useState(SANDBOX_ROSTER_INITIAL);
  const [realmFrom] = useState("Upper Citadel");
  const [realmTo, setRealmTo] = useState("Lower Catacombs");

  const setStatus = (id, status) =>
    setRoster((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)));

  const removeChar = (id) => setRoster((prev) => prev.filter((c) => c.id !== id));

  const addYourself = () => {
    if (roster.some((c) => c.avatar)) return;
    setRoster((prev) => [...prev, { id: `s_you_${Date.now()}`, name: "YOU", role: "Self-Avatar", status: "ACTIVE", location: "Cloud City", avatar: true, locked: false }]);
  };

  const addCustom = () => {
    setRoster((prev) => [...prev, { id: `s_new_${Date.now()}`, name: `New Character ${prev.length + 1}`, role: "Introduced mid-story", status: "ACTIVE", location: "Cloud City", avatar: false, locked: false }]);
  };

  return (
    <div>
      <div className="se-eyebrow">Screen 07 · World Control Sandbox</div>
      <h1 className="se-h1">Bend the universe to your will</h1>
      <p className="se-sub">
        The founding cast you locked at story start can't have their identity edited here — only their status
        and location. Insert yourself, introduce brand-new characters, shift the active realm, or soft-reboot
        into a new arc while keeping the characters you care about.
      </p>

      <div style={{ display: "flex", gap: 10, marginBottom: 22 }}>
        <button className="se-btn se-btn-violet" onClick={addYourself}><UserPlus size={14} /> Add yourself as character</button>
        <button className="se-btn se-btn-ghost" onClick={addCustom}><Plus size={14} /> Create custom character</button>
        <button className="se-btn se-btn-ghost"><MapPin size={14} /> Change current realm</button>
      </div>

      <div className="se-card">
        <div className="se-section-label"><Users size={13} /> Character roster &amp; state editing</div>
        <table className="se-table">
          <thead>
            <tr><th>Character</th><th>Cast</th><th>Role</th><th>Status</th><th>Location</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {roster.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>{c.avatar ? "👤 " : ""}{c.name}</td>
                <td><LockPill isNew={!c.locked} /></td>
                <td className="se-concept-summary" style={{ padding: 0 }}>{c.role}</td>
                <td><Badge status={c.status} /></td>
                <td className="se-concept-summary" style={{ padding: 0 }}>{c.location}</td>
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    {!c.locked && (
                      <button className="se-btn se-btn-ghost se-btn-sm"><Edit3 size={11} /> Edit</button>
                    )}
                    {c.status !== "DECEASED" ? (
                      <button className="se-btn se-btn-danger se-btn-sm" onClick={() => setStatus(c.id, "DECEASED")}><Skull size={11} /> Kill</button>
                    ) : (
                      <button className="se-btn se-btn-ghost se-btn-sm" onClick={() => setStatus(c.id, "ACTIVE")}><Heart size={11} /> Revive</button>
                    )}
                    {!c.avatar && !c.locked && (
                      <button className="se-btn se-btn-ghost se-btn-sm" onClick={() => removeChar(c.id)}><Trash2 size={11} /></button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="se-two-col se-mt">
        <div className="se-card">
          <div className="se-section-label"><MapPin size={13} /> Current location / realm</div>
          <div className="se-realm-flow">
            <select className="se-select" value={realmFrom} disabled>{REALMS.map((r) => <option key={r}>{r}</option>)}</select>
            <ArrowRight size={16} color="var(--ink-faint)" />
            <select className="se-select" value={realmTo} onChange={(e) => setRealmTo(e.target.value)}>
              {REALMS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <div className="se-card">
          <div className="se-section-label"><RotateCcw size={13} /> Universe restart</div>
          <p className="se-concept-summary" style={{ marginBottom: 12 }}>Wipes chapter progress, keeps the characters and relationships you select.</p>
          <button className="se-btn se-btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={() => goTo("arcpreview")}>
            <RotateCcw size={15} /> Launch new story arc
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 6B — Arc premise selection                                       */
/* ---------------------------------------------------------------------- */

function Screen6B({ goTo }) {
  const [selected, setSelected] = useState("opt_1");
  const [premise, setPremise] = useState(ARC_OPTIONS[0].summary);
  const [objectives, setObjectives] = useState(ARC_OPTIONS[0].objectives);
  const [newObj, setNewObj] = useState("");
  const [loading, setLoading] = useState(false);

  const pick = (opt) => {
    setSelected(opt.id);
    setPremise(opt.summary);
    setObjectives(opt.objectives);
  };

  const addObjective = () => {
    if (!newObj.trim()) return;
    setObjectives((prev) => [...prev, newObj.trim()]);
    setNewObj("");
  };

  const launch = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); goTo("workspace"); }, 900);
  };

  return (
    <div>
      <div className="se-eyebrow">Screen 07B · New Arc Premise</div>
      <h1 className="se-h1">Choose &amp; edit your premise</h1>
      <p className="se-sub">
        <span className="se-mono" style={{ color: "var(--amber)" }}>Retained realm: Lower Catacombs</span>
        {"  ·  "}Active roster: Kael, Lyra, YOU
      </p>

      <div className="se-section-label"><Sparkles size={13} /> Step 1 — Select a story arc direction</div>
      <div className="se-arc-grid">
        {ARC_OPTIONS.map((opt) => (
          <div key={opt.id} className={`se-concept-card ${selected === opt.id ? "selected" : ""}`} onClick={() => pick(opt)}>
            <div className="se-flex-between">
              <span className="se-concept-title" style={{ fontSize: 15 }}>{opt.title}</span>
              {selected === opt.id && <Check size={15} color="var(--amber)" />}
            </div>
            <p className="se-concept-summary">{opt.summary}</p>
          </div>
        ))}
      </div>

      <div className="se-card">
        <div className="se-section-label"><Edit3 size={13} /> Step 2 — Edit selected premise &amp; objectives</div>
        <label className="se-charcount">Arc pitch / premise</label>
        <textarea className="se-textarea" style={{ marginBottom: 16 }} value={premise} onChange={(e) => setPremise(e.target.value)} />
        <label className="se-charcount">Key objectives</label>
        <div style={{ marginTop: 8, marginBottom: 4 }}>
          {objectives.map((o, i) => (
            <span key={i} className="se-obj-tag">
              🏷️ {o}
              <button onClick={() => setObjectives((prev) => prev.filter((_, idx) => idx !== i))}><X size={12} /></button>
            </span>
          ))}
          <span className="se-obj-tag" style={{ background: "transparent", cursor: "text" }}>
            <input value={newObj} onChange={(e) => setNewObj(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addObjective()}
              placeholder="Add objective…" style={{ background: "transparent", border: "none", color: "var(--ink)", fontSize: 12, width: 110, outline: "none" }} />
            <button onClick={addObjective}><Plus size={12} /></button>
          </span>
        </div>
      </div>

      <div className="se-flex-between se-mt">
        <button className="se-btn se-btn-ghost" onClick={() => goTo("sandbox")}>← Back to sandbox</button>
        {loading ? (
          <LoadingLine text="Spinning up the new arc…" />
        ) : (
          <button className="se-btn se-btn-primary" onClick={launch}>
            <Zap size={15} /> Confirm &amp; launch story arc
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Screen 7 — AI Agents: story evaluator + business/interest agent         */
/* ---------------------------------------------------------------------- */

function Screen7() {
  const [loading, setLoading] = useState(false);
  const [ranAt, setRanAt] = useState("Chapter 2");

  const rerun = () => {
    setLoading(true);
    setTimeout(() => { setLoading(false); setRanAt("Chapter 2 (re-checked)"); }, 900);
  };

  return (
    <div>
      <div className="se-eyebrow">Screen 08 · AI Agents</div>
      <h1 className="se-h1">Let the agents watch your story</h1>
      <p className="se-sub">
        The Evaluator Agent checks whether every character and world detail still matches what was locked in at
        the start. The Business Agent judges whether the story is actually landing with readers.
      </p>

      <div className="se-flex-between" style={{ marginBottom: 18 }}>
        <span className="se-charcount">Last run: {ranAt}</span>
        {loading ? <LoadingLine text="Re-running agents…" /> : (
          <button className="se-btn se-btn-ghost" onClick={rerun}><RefreshCw size={13} /> Re-run both agents</button>
        )}
      </div>

      <div className="se-agent-grid">
        <div className="se-agent-card">
          <div className="se-agent-head">
            <ShieldCheck size={18} color="var(--teal)" />
            <span className="se-agent-title">Evaluator Agent</span>
          </div>
          <div className="se-agent-sub">Checks character &amp; world consistency against the locked cast</div>

          {EVALUATOR_REPORT.overallStatus === "IN_SYNC" ? (
            <div className="se-badge se-badge-active" style={{ marginBottom: 14 }}><ShieldCheck size={11} /> Story is fully in sync</div>
          ) : (
            <div className="se-badge se-badge-deceased" style={{ marginBottom: 14 }}><AlertTriangle size={11} /> Minor divergence detected</div>
          )}

          <div className="se-section-label" style={{ marginTop: 4 }}><Users size={12} /> Character sync</div>
          {EVALUATOR_REPORT.characters.map((c) => (
            <div key={c.name} className="se-sync-row">
              <SyncBadge status={c.status} />
              <div>
                <div className="se-sync-name">{c.name}</div>
                <div className="se-sync-note">{c.note}</div>
              </div>
            </div>
          ))}

          <div className="se-section-label" style={{ marginTop: 16 }}><Layers size={12} /> World facts</div>
          {EVALUATOR_REPORT.worldFacts.map((w) => (
            <div key={w.label} className="se-sync-row">
              <SyncBadge status={w.status} />
              <div className="se-sync-name" style={{ marginBottom: 0 }}>{w.label}</div>
            </div>
          ))}
        </div>

        <div className="se-agent-card">
          <div className="se-agent-head">
            <TrendingUp size={18} color="var(--amber)" />
            <span className="se-agent-title">Business Agent</span>
          </div>
          <div className="se-agent-sub">Judges whether the story is interesting enough to keep readers hooked</div>

          <div className="se-flex-between" style={{ marginBottom: 18, alignItems: "flex-end" }}>
            <div>
              <div className="se-score-big">{BUSINESS_REPORT.score}</div>
              <div className="se-score-label">Interest score / 100</div>
            </div>
            <div style={{ textAlign: "right", maxWidth: 180 }}>
              <div className="se-concept-tag" style={{ marginBottom: 0 }}>"{BUSINESS_REPORT.verdict}"</div>
            </div>
          </div>

          <div className="se-section-label"><Gauge size={12} /> Breakdown</div>
          {BUSINESS_REPORT.breakdown.map((b) => (
            <ScoreBar key={b.label} label={b.label} score={b.score} />
          ))}

          <div className="se-section-label" style={{ marginTop: 12 }}><MessageSquare size={12} /> Notes</div>
          <p className="se-concept-summary">{BUSINESS_REPORT.note}</p>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* App shell                                                               */
/* ---------------------------------------------------------------------- */

const NAV = [
  { id: "seed", num: "01", label: "Seed & Input", icon: Sparkles },
  { id: "concepts", num: "02", label: "Concept Selection", icon: Brain },
  { id: "characters", num: "03", label: "Cast & Characters", icon: UserPlus },
  { id: "workspace", num: "04", label: "Narrative Workspace", icon: BookOpen },
  { id: "comic", num: "05", label: "Comic Studio", icon: ImageIcon },
  { id: "progression", num: "06", label: "Progression & Volume", icon: GitBranch },
  { id: "sandbox", num: "07", label: "World Sandbox", icon: Users },
  { id: "arcpreview", num: "7B", label: "New Arc Premise", icon: RotateCcw },
  { id: "agents", num: "08", label: "AI Agents", icon: ShieldCheck },
];

export default function StoryEngineProto() {
  const [screen, setScreen] = useState("seed");

  const renderScreen = () => {
    switch (screen) {
      case "seed": return <Screen1 goTo={setScreen} />;
      case "concepts": return <Screen2 goTo={setScreen} />;
      case "characters": return <ScreenCharacters goTo={setScreen} />;
      case "workspace": return <Screen3 goTo={setScreen} />;
      case "comic": return <Screen4 goTo={setScreen} />;
      case "progression": return <Screen5 goTo={setScreen} />;
      case "sandbox": return <Screen6 goTo={setScreen} />;
      case "arcpreview": return <Screen6B goTo={setScreen} />;
      case "agents": return <Screen7 goTo={setScreen} />;
      default: return null;
    }
  };

  return (
    <div className="se-root">
      <style>{CSS}</style>
      <nav className="se-nav">
        <div className="se-brand">
          <DialLogo />
          <div>
            <div className="se-brand-name">Story Engine</div>
            <div className="se-brand-tag">CLICKABLE PROTOTYPE</div>
          </div>
        </div>
        {NAV.map((item) => (
          <button key={item.id} className={`se-nav-item ${screen === item.id ? "active" : ""}`} onClick={() => setScreen(item.id)}>
            <span className="se-nav-num">{item.num}</span>
            <item.icon size={14} />
            <span className="se-nav-label">{item.label}</span>
          </button>
        ))}
        <div className="se-nav-foot">
          All content on this screen is placeholder data for pitching purposes. No backend or LLM calls are made.
        </div>
      </nav>
      <main className="se-main">{renderScreen()}</main>
    </div>
  );
}
