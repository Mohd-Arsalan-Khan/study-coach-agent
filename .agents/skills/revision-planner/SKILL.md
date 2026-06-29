---
name: revision-planner
description: Creates a personalized revision plan based on the user's quiz performance and weak areas. Use this when the user asks for a study plan, revision schedule, or what to study next. Do NOT use for generating questions.
---

# Revision Planner Skill

## Goal
Analyze the user's quiz history and weak areas to create a realistic, 
structured revision plan they can actually follow.

## Instructions
1. Read weak_areas and quiz_scores from agent state
2. Rank topics by score (lowest first — most urgent)
3. Generate a 3-day revision plan:
   - Day 1: Focus on the 2 weakest topics (45 mins each)
   - Day 2: Review Day 1 topics + introduce 1 new weak topic
   - Day 3: Mixed practice across all weak topics + mini quiz
4. For each session include:
   - Topic name
   - Suggested study method (re-read notes / watch video / practice questions)
   - Time allocation in minutes
   - Key concepts to focus on
5. End with 3 motivational tips specific to the topics being studied
6. Output as a clean structured markdown table

## When NOT to use this skill
- When user wants quiz questions
- When user wants topic explanations
- When no quiz data exists yet (prompt user to take a quiz first)
