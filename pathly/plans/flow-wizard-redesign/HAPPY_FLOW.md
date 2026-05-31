---
name: Happy Flow
---
# flow-wizard-redesign - Happy Flow

## Overview

A developer wants to create a standard pipeline flow. They open the wizard, pick a template, confirm the stages, assign agents, review the live YAML, and save.

## Step-by-Step Happy Flow

### Step 1: Open the wizard
- User opens the FlowWizard
- System shows Step0Entry with three cards and, if present, a resume draft card

### Step 2: Choose a starting point
- User clicks From template and selects Standard pipeline
- System seeds states and transitions, then advances to Step 1

### Step 3: Name the flow
- User enters a valid flow name and optional description
- System validates the name and advances when Next is clicked

### Step 4: Define stages
- User reviews the stages and optionally reorders them
- System keeps the pipeline chain in sync and auto-generates transitions if needed

### Step 5: Assign agents
- User assigns agents to non-terminal states
- System warns, but does not block, if a non-terminal state is unassigned

### Step 6: Quality & routing
- User leaves the accordion sections collapsed because no gates or routing rules are needed
- System preserves the empty quality data in the YAML output

### Step 7: Review and save
- User reviews the live YAML preview and clicks Save Flow
- System writes the YAML to disk and closes the wizard

## End State

The developer has a valid flow YAML file written to disk without manually authoring YAML.
