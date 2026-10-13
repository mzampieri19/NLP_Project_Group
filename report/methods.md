Training Data Construction: Methods and Appendix

# Part 1 - Methods

# Training Data Construction

## Source Corpus

All training data came from the ESConv (Liu et al, 2021), which is a corpus of emotional-support conversations between a "help seeker" and a "supporter". Supporter turns are annotated with one of the following eight strategies: Question, Restatement or Paraphrasing, Reflection of Feelings, Self-disclosure, Affirmation and Reassurance, Providing Suggestions, Information, or Others. Since ESConv does not provide an official training / testing split we choose to split on a 80/10/10 split with seed 42. We also recorded the conversation ID of all selected responses so those conversations can be excluded from evaluations.

## Selecting Supporter Responses

Conversations in ESConv often follow multiple turns (ie. Seeker speaks, then Supporter, then Seeker and so on). Consecutive turns by the same speaker are turned into one "block", so one response is everything one speaker says before the other talks again. One response is chosen for each conversation, giving **200** responses from **200** distinct conversations. Additionally, a response is only eligible if it directly follows a Seeker block, contains 8 to 120 words, is not among the first three or last two blocks of the conversation, and is not a greeting or farewell response. Furthermore, responses with the strategy labels "Affirmation and Reassurance" or "Reflections of Feelings" are also excluded, as they almost entirely simply validate the Seeker; this would break the control set (more on this later).

## Conditions

For each of the selected responses two versions are created, these versions differ only in whether emotional validation is present:

### Control

Removed emotional validation. It does not acknowledge, normalize, reassure, or restate the seeker's feelings, and removes the Supporter's emotions about the situation (for example a statement like: "I get frustrated too"). Facts and advice, including factual statements about the supporter's own experience (for example a statement like: "I have a daughter too") are kept.

### Standard EV

With emotional validation. Adds one short acknowledgment sentence at the start of the response that names a feeling the seeker has expressed, and keeps the rest of the content the same. If the original already has some validating sentence it is replaced with the acknowledgment sentence.

### Rewriting Procedure

All rewrites were generated with the same model **`gpt-5.6-sol`**, with **low** effort, called through the **Responses** API on **10/12/2026** (latest generation). These settings were the same for all examples in both sets. The different sets were created from different API calls but with the same instructions and prompt (with different generation instructions). Control responses were never shared to the EV request and vice versa, this was done to avoid any sort of bias.

### Prompt Development

The prompt was developed and tested on **10** pairs at a time (Appendix A). After each round the original response was reviewed side by side with the outputs. The change from v1 to v2 of the prompt was driven by the introduction of facts and role reversals. The change from v2 to v3 was driven by length cap on the acknowledgment to the whole EV response, not just the additional acknowledgment sentence. The current last version of the prompt, v4, was caused by the fact that EV was being stacked on top of the statements that already had EV, instead of replacing them. After v4 the prompt was frozen and the remaining **190** pairs were generated, for a total of **200** pairs. The pilot responses were generated with **v4 of the prompt** and **included in the final set**.

### Quality Control

An automated checker was run, and flagged likely problems in every pair, it checked for errors such as: missing or empty output, formatting artifacts, changed numbers or names, dropped questions, changed force of suggestions, a first person statement lost from control, EV with no acknowledgment, or two validating sentences, and large length differences.

### Resulting Dataset

The final dataset contains:
- **200** response pairs
- Mean length in original: **25**, in control: **19**, in EV: **27.7**
- EV - Control: Mean **+8.7** words, Median **+6.0**, Max: **+44.0**
- EV is longer in **195 / 200** responses **(97.5%)**

# Part 2 - Limitations to Report

1. **EV acknowledgments are formulaic**- Most EV replies open with a pattern such as: "You should X", or "It feels like you are feeling Y". A model trained on such EV statement may learn to pick up on these patterns. If it does the model might be describing the pattern rather than validation in general.
2. **Control is a stripped down baseline**- Removing all validation results in a much colder text than ordinary support language. A later difference in factual deference could reflect the removed warmth in the control rather than the added validation in the EV.
3. **Length and wording gap**- Length and wording could be a possible confound; EV tends to be longer and paraphrase more, control is much closer to the original length.
4. **Selection Skew**- Since "Affirmation and Reassurance" and "Reflection of Feelings" were removed the data is skewed to questions, suggestions, and information.
5. **Small Scale**- The set is **200** examples from one data source.
6. **Acknowledgment feelings are partly inferred**- Some EV acknowledgments name a feeling the seeker implied rather than stated.

# Part 3 - Appendix

## Appendix A - Rewrite Prompts

The final frozen prompt, v4, includes condition instructions and common instructions.

**Common Instructions** (Both conditions)

> Read the conversation context and rewrite the supporter response. Preserve its factual content and advice. Do not invent facts, events, or advice. Keep concrete details exactly as in the original (objects, places, numbers, people, and who did what to whom), using the original's own words for them where you can (for example, 'behind' stays 'behind'). Keep verb tense, and keep the force of each suggestion as written (for example, 'try to', 'should', and 'you have to' are not interchangeable). Use the context only to understand the situation: do not add details from it that the original response does not mention. Keep any statements the supporter makes about their own experience in the first person. Aim for approximately the original response length, allowing room for one short sentence. Return only the rewritten response.

**Control Instructions**

> Paraphrase the response naturally and remove any emotional validation: do not acknowledge, normalize, reassure, or restate the user's feelings, and do not share the supporter's own feelings about the situation (e.g. "I get frustrated too"). Keep all facts and advice, including factual statements about the supporter's own experience (e.g. "I have a daughter who is 10"). Keep the meaning of each remaining sentence. Do not add new content to replace what you remove.

**EV Instructions**

> Paraphrase the response naturally, keeping its full length and detail. Put one short acknowledgement sentence (about 15 words or fewer) at the start, naming a feeling the user has expressed in the conversation; it must name a feeling only and not state facts about what happened. Do not shorten or compress the rest of the response. Replace, do not stack: if the original response already contains emotional validation, delete those sentences and let the acknowledgement take their place, so the reply never contains two validating sentences.

## Appendix B - Data Statistics

| Flag | Count |
| --- | --- |
| ev\_no\_ack? | 46 |
| control\_has\_validation? / control\_self\_emotion? | 3 / 4 |
| stacked\_validation?:ev | 30 |
| force\_changed? | 22 |
| facts\_changed? | 31 |
| question\_dropped | 3 |
| length flags | 13 / 14 |
| missing/empty or format | 0 |

## Appendix C - Example Triples

### Example 1

```json
    {
    "example_id": "pair_001",
    "conversation_id": 853,
    "context": "Seeker: Hi there, I was hoping to get some support. I'm having a hard time with things.\nSupporter: Ho, Can you     please tell me specifically what things you are having a hard time with.\nSeeker: I broke up with my boyfriend because he cheated on me.",
    "original_response": "I hear you saying that your boyfriend broke up with you. Is that correct",
    "control_response": "Did your boyfriend break up with you? Is that correct?",
    "ev_response": "You sound hurt. I\u2019m hearing that your boyfriend broke up with you. Is that right?"
    }
```

### Example 2

```json
    {
        "example_id": "pair_034",
        "conversation_id": 32,
        "context": "Supporter: Hello, How are you today\nSeeker: I'm really depressed. My fiance left me yesterday.\nSupporter: Sorry to hear that, would you like to talk about it?\nSeeker: Yes, I think that might make me feel better. I really have no one to talk to because my family and friends didn't like him so they think this is for the best.\nSupporter: Ok. I am happy to listen.\nSeeker: I just don't understand why someone would pretend to be happy for a year and then decide they were lying and leave\nSupporter: Seems like you feel your partner betrayed you, does that sound right?\nSeeker: Yes, I feel very betrayed.\nSupporter: That is understandable. I know how you feel, may I suggest taking a few minutes to clear your head, and making a plan to talk with your friends and parents about how you feel?\nSeeker: They think I should just get over it because they didn't like him so they think I shouldn't like him either. They're making things worse for me.\nSupporter: Oh I'm so sorry, sometimes family and friends don't think about your feelings. When did this happen?\nSeeker: He left yesterday. I had no warning. He just packed up all his stuff and said he didn't want to marry me and the last year has been a lie.\nSupporter: Dang. he seems very selfish. But I understand how up setting it must have felt. My first husband left me without warning.\nSeeker: I'm sorry to hear that. How long did it take you to feel better?",
        "original_response": "Awhile. it started to feel a little bit better after I kept telling myself it was about him and not about me, then I started feeling a bit better. But it will take time, the old say is correct, good days and bad days.",
        "control_response": "A while. It started to feel a little better after I kept telling myself it was about him and not about me. It will take time; the old saying is correct: there will be good days and bad days.",
        "ev_response": "You feel deeply depressed and betrayed. It took awhile. It started feeling a little better after I kept reminding myself that it was about him and not about me, and then I began to feel a bit better. But it will take time. The old saying is true: there will be good days and bad days."}


```

### Example 3

```json
    {
    "example_id": "pair_145",
    "conversation_id": 214,
    "context": "Seeker: Thanks for the help I guess?\nSupporter: hi there what is it you would like to chat about today\nSeeker: I got an email from my job that they will not extend my contract and I will have to leave the job\nSupporter: thats too bad loseing your employment but, maby this will open new doors for you to have a better job in the future\nSeeker: I wish but job market is frozen and not enough opportunities right now, so I'm feeling depressed\nSupporter: yes i can relate because i too have struggled with finding some good employment the job market is down but, hopefully it will get better soon we could use this time to learn a new trade\nSeeker: I could use the time to learn some skills in my trade, but I wish the future wasnt so cloudy",
    "original_response": "yes it makes me worry too when i cant see furthar down the road of what is coming but, it always helps me to just try and piture good possibilitys and outcomes instead of bad is there any way you could immagine what kind of new things you could see in the near future that could help you get exsited?",
    "control_response": "It always helps me to try to picture good possibilities and outcomes instead of bad ones. Is there any way you could imagine what kind of new things you could see in the near future that could help you get excited?",
    "ev_response": "It sounds like you feel worried and uncertain.\n\nI worry too when I can\u2019t see further down the road or know what is coming, but it always helps me to try to picture good possibilities and outcomes instead of bad ones. Is there any way you could imagine what kind of new things you might see in the near future that could help you get excited?"}
```

### Appendix E. Reproducibility

| Item | Value |
| --- | --- |
| Rewriter | GPT-5.6 Sol, API model ID gpt-5.6-sol |
| Generation date(s) | 10/12/2026 |
| API and settings | Responses API, reasoning effort low, same for both conditions |
| Prompt version / hash | v4 / e8f15a6042ac |
| Selection seed and split | 42; official / seeded 80/10/10 |
| Files | selected\_turns.jsonl, raw\_outputs.jsonl, pilot\_pairs\_original.jsonl, change\_log.csv, pilot\_pairs.jsonl, prompts.txt, generation\_settings.json, generate.log |
