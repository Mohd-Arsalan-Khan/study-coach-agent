---
name: quiz-generator
description: Generates quiz questions from study notes or a specific topic. Use this when the user wants to be tested, quizzed, or practice questions on any subject. Do NOT use for general Q&A conversations or explanations.
---

# Quiz Generator Skill

## Goal
Generate high-quality quiz questions from the user's study notes that test 
real understanding, not just memorization.

## Instructions
1. Load the relevant topic from the RAG index in state
2. Generate exactly 5 questions mixing these types:
   - 2 multiple choice questions (4 options each)
   - 2 short answer questions  
   - 1 application question (apply the concept to a real scenario)
3. For each question include:
   - The question text
   - The correct answer
   - A brief explanation of why it is correct
   - Difficulty level (easy/medium/hard)
4. Prioritize topics where the user scored below 60% in previous sessions
5. Output questions as structured JSON

## When NOT to use this skill
- When user asks for an explanation of a topic
- When user wants a revision plan
- When user is having a general conversation
