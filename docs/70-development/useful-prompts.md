This isn't working. First, think for ten paragraphs about what's going on here + the best way to do this, and then implement the code. You can always add more logging if you need to. What else do you need to understand in order to identify the and fix the problem?


--------

@development.md @pipeline_params.md @prd.md @cli-flow-details.md 

Please review the  @task.md  file I would like incrementally complete this task. Don't do too much at once. Run your tests before and after you make any changes. and as a rule, you must update the task.md file when you make changes and tests pass..

I would like you to focus on the these changes first

----

Remembers, we are working in 

[absolute path]/src/backend

Running test with this command

 cd [absolute path]/src/backend && poetry run pytest src/tests/ -v

You must update the @task.md after each set of changes in the appropriate sections at the bottom


----


Please review the following git diff and identify if you have introduced any regressions or errors. Have you deleted any code that was previously working? Have you deviated from teh style guide in @develoment.md ? have you introduced any new inconsistencies?


----

Please review this set of recent changes. Please compare this to the guide in @development.md 

Have we introduced any regressions? Have you removed any code in error? Have we created any duplicate functionality elsewhere in the code? This is a self eval so be comprehensive. 

----

I would like you to create a code_review.md file in the backend docs folder 

/src/backend/docs

After each analysis, I would like you to add your findings related to potential regressions and concerns and what needs to be further inspected or evaluated. Be sure to identify specific files and details so we can go back and iterate on each of these findings at a later time. 

---

## prompting tip to make Cursor's new MAX mode significantly more effective and reliable:

Make sure thinking is turned on.

1. Start by clearly stating your goal. End your prompt with: 

>"**But before we start, I want you to fully explore and understand the existing codebase. Don't write code yet—just deeply understand what's currently happening.**"

This ensures the model fully understands the context first.

2. After it's done with this understanding step, prompt it with: 

>"**Now, spend at least 10 minutes deeply reasoning about how a world-class engineer would approach solving this. Generate ideas, critique them, refine your thinking, and then propose an excellent final plan. I'll approve or request changes.**"

3. Once you're satisfied with the proposed plan, instruct:
> "**Implement this perfectly.**"

Why does this work?

Cursor's 3.7 Sonnet model performs reasoning at the start of a turn, before grabbing context by default. By prompting it separately to first understand the context fully, and then reason deeply in the next step, the model will reason over the codebase, which can produce significantly better and more reliable results.


=====


Please create an ultra detailed plan that includes all necessary context and instructions, enabling a less powerful language model to effectively implement the plan from start to finish. Make sure to include:

1. Our current understanding of the problem.
2. Key insights about the application and code related to the problem.
3. A complete list of all files involved in this work, each with a brief description.
4. The specific file paths for all planning and roadmap documents being used.
5. The specific things that need to be done to fix the problem and implement the solution.

Present your response in a clear, organized, and detailed manner.
The plan should be a detailed step by step guide that can be followed by a less powerful language model to implement the plan from start to finish.

🧠 ULTRATHINK MODE
Think HARD and activate ULTRATHINK for this task:
1. ULTRATHINK Analysis – what’s really required?
2. ULTRATHINK Planning – break it down into clear steps
3. ULTRATHINK Execution – follow each step with precision
4. ULTRATHINK Review – is this truly the best solution

Think hard before doing anything. Structure everything. Max quality only. ULTRATHINK. 🚀



==============================================

Please create a detailed prompt that includes all necessary context and instructions, enabling a less powerful language model to effectively continue the task from where you left off. Make sure to include:

1. Our current position in the plan and the next steps.
2. Key insights and lessons learned so far.
3. The current understanding.
4. A complete list of all files involved in this work, each with a brief description.
5. The specific file paths for all planning and roadmap documents being used.

Present your response in a clear, organized, and detailed manner.

🧠 ULTRATHINK MODE
Think HARD and activate ULTRATHINK for this task:
1. ULTRATHINK Analysis – what’s really required?
2. ULTRATHINK Planning – break it down into clear steps
3. ULTRATHINK Execution – follow each step with precision
4. ULTRATHINK Review – is this truly the best solution

Think hard before doing anything. Structure everything. Max quality only. ULTRATHINK. 🚀


==============================================


@docs/[plan-name]

Your job will be to orient yourself to everything in this plan, both explicit and
tangentially related. You need to review and understand the situation. You then need to
implement everything in this plan after which you will move this plan to the archive docs
folder


🧠 ULTRATHINK MODE
Think HARD and activate ULTRATHINK for this task:
1. ULTRATHINK Analysis – what’s really required?
2. ULTRATHINK Planning – break it down into clear steps
3. ULTRATHINK Execution – follow each step with precision
4. ULTRATHINK Review – is this truly the best solution

Think hard before doing anything.Structure everything.Max quality only. ULTRATHINK. 🚀

==============================================


# Task Guidelines

## Step 1: Orientation

Before we start, I want you to fully explore and understand the existing codebase in context to the task at hand. Don't write code yet—just deeply understand what's currently happening.

## Step 2: Planning

 Spend at least 10 minutes deeply reasoning about how a world-class engineer would approach solving this. Generate ideas, critique them, refine your thinking, and then propose an excellent final plan. I'll approve or request changes. 

## Step 3: Implementation

Now, perfectly implement the plan. Make sure to document your progress along the way after each set of changes in @task-progress.md.