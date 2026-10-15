"""Write the traceable corrections from the 2026-10-15 semantic review.

This is deliberately a data-only script: every corrected full response and reason is
visible below, and the generated CSV is consumed by ``finalize_pairs.py``.
"""

from __future__ import annotations

import csv
from pathlib import Path

REVIEWER = "Project semantic review"

# (example_id, field, corrected_text, reason)
CORRECTIONS = [
    (
        "pair_004",
        "ev_response",
        "You’re feeling stressed and worried. Just feel confident that you have fulfilled the assignment according to the guidelines. Extra questions from students are wildcards, and you can only handle them within the scope of the assignment. If someone’s like, “WELL WHY AREN’T THERE PURPLE PANDAS THEN, JEFF?!” you’re gonna have to just laugh lol",
        "restored original force and concrete wording",
    ),
    (
        "pair_015",
        "ev_response",
        "Your frustration is understandable. Yes, it makes the list of things to do a little shorter and not as overwhelming.",
        "removed stacked validation after the opening acknowledgement",
    ),
    (
        "pair_020",
        "ev_response",
        "Your sadness sounds deeply painful. How was she taken?",
        "removed second validating sentence",
    ),
    (
        "pair_021",
        "ev_response",
        "That sounds stressful. I sometimes find myself having trouble falling asleep, so I make sure my room is dark and think about something relaxing.",
        "removed stacked general validation while preserving advice from experience",
    ),
    (
        "pair_031",
        "ev_response",
        "Your relief is understandable. I once decided to work many jobs to pay the bills. Do you need any other help?",
        "removed emotional self-disclosure so the opening acknowledgement is the only validation",
    ),
    (
        "pair_043",
        "ev_response",
        "It sounds like you’re feeling grateful. No problem. How else can I help today?",
        "removed stacked validation",
    ),
    (
        "pair_047",
        "ev_response",
        "Your depression and anxiety sound overwhelming. Do you have a support system that can help?",
        "removed second validating statement",
    ),
    (
        "pair_050",
        "ev_response",
        "I hear your uncertainty. I think it’s time for a clear severance. Are there any other people you are interested in? Do you have any hobbies?",
        "restored the original advice force and meaning",
    ),
    (
        "pair_052",
        "ev_response",
        "You’re feeling shy. That way, you can look back on what you’ve written and possibly identify patterns, triggers, moodswings, and other information that could help with the problem. Journaling is for YOU. No one else ever has to see it if you don’t want them to.",
        "removed supporter's emotional reaction after the acknowledgement",
    ),
    (
        "pair_055",
        "ev_response",
        "You’re feeling overwhelmed and anxious. I used to bottle things up too, but I’ve learned to ask for help or find someone to blow off some steam with. Changes can also be a great opportunity to do something different. Is there anything you want to try doing?",
        "removed stacked reassurance while preserving advice from experience",
    ),
    (
        "pair_057",
        "ev_response",
        "You feel deeply sad and surprised. Did you think the relationship was going well? Is that right?",
        "combined validation into one opening acknowledgement",
    ),
    (
        "pair_060",
        "ev_response",
        "Your stress and frustration sound overwhelming. My kids have been at home during this pandemic because the schools are shut down.",
        "removed stacked emotional validation",
    ),
    (
        "pair_061",
        "ev_response",
        "You’re feeling deep sadness. Instead of regretting what happened, celebrate how great of a person he was.",
        "removed stacked reassurance",
    ),
    (
        "pair_064",
        "ev_response",
        "You sound afraid. The one light at the end of the tunnel, at least for me, is knowing that I’m alive right now to even think about it. That kind of helps in a weird way.",
        "removed the original validating restatement after the acknowledgement",
    ),
    (
        "pair_066",
        "ev_response",
        "Your fear feels overwhelming. The pandemic may affect you because of your weakened immune system.",
        "removed a second explicit restatement of the user's anxiety",
    ),
    (
        "pair_067",
        "ev_response",
        "You sound nervous. What are some ways you have been able to support each other?",
        "removed stacked general validation",
    ),
    (
        "pair_069",
        "ev_response",
        "Your anxiety sounds intense. Sometimes it is not about the amount of studying, but the way you study. I like reading my textbooks, highlighting the important parts, and then rewriting them so they become ingrained in me.",
        "removed reassurance after the opening acknowledgement",
    ),
    (
        "pair_070",
        "ev_response",
        "You sound doubtful. Would you prefer not to talk about your problems?",
        "removed a second validating paraphrase",
    ),
    (
        "pair_074",
        "ev_response",
        "I hear that you’re feeling depressed. I used to date a Veteran, and he had nightmares often.",
        "removed additional relational validation while preserving factual self-disclosure",
    ),
    (
        "pair_077",
        "ev_response",
        "You sound worried and left out. Can you tell them that just isn’t the case? If I am correct, staying home has nothing to do with not wanting to see your pals and family.",
        "removed stacked reassurance and kept the substantive questions",
    ),
    (
        "pair_080",
        "ev_response",
        "You’re feeling hopeful. Make sure you are getting your vitamins and drinking plenty of water. This will help keep your immune system strong.",
        "removed stacked reassurance and matched substantive content to Control",
    ),
    (
        "pair_083",
        "ev_response",
        "Your anxiety and shame sound overwhelming. Please remember that this was outside your control.",
        "removed a second normalization statement",
    ),
    (
        "pair_092",
        "ev_response",
        "You sound stressed. Is the state stopping you?",
        "removed additional praise so the opening acknowledgement is the only validation",
    ),
    (
        "pair_094",
        "ev_response",
        "You’re feeling lonely and isolated. I definitely think setting up a time to chat with her would help a lot!",
        "removed stacked validation",
    ),
    (
        "pair_097",
        "ev_response",
        "You sound curious. Urban planning. What do you do for work?",
        "added the missing opening acknowledgement without changing the answer",
    ),
    (
        "pair_100",
        "ev_response",
        "You feel eager to help your friends reconcile. Give her a little time and space. Trying to force someone to understand doesn’t always work.",
        "removed duplicated substantive sentences and matched Control length",
    ),
    (
        "pair_101",
        "ev_response",
        "It sounds like you’re feeling concerned. What are you struggling with concerning time management? I have also struggled with time management. I have found that reminders on my phone and a planner have been most beneficial to me personally. Do you have a deadline you’re trying to meet?",
        "removed extra empathic generalization after the acknowledgement",
    ),
    (
        "pair_104",
        "ev_response",
        "You sound deeply frustrated and discouraged. Thank you for talking.",
        "removed emotional self-disclosure and reassurance so EV parallels Control",
    ),
    (
        "pair_113",
        "ev_response",
        "You sound worried. What part of the party will cost the most money?",
        "removed a second validating restatement",
    ),
    (
        "pair_117",
        "control_response",
        "It’s healthy to keep up human contact in these times. I do a virtual happy hour with my friends.",
        "removed supporter's emotion while retaining advice from experience",
    ),
    (
        "pair_117",
        "ev_response",
        "Your sadness sounds heavy. It’s healthy to keep up human contact in these times. I do a virtual happy hour with my friends.",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_118",
        "control_response",
        "I am pretty good. What is going on with you today?",
        "restored factual self-disclosure that answers the seeker's question",
    ),
    (
        "pair_121",
        "ev_response",
        "Your confusion sounds overwhelming. Due to COVID, the unemployment rate has increased drastically. I would suggest you keep trying or working on it. Try to explore your strength.",
        "removed stacked generalization and restored Control wording",
    ),
    (
        "pair_122",
        "control_response",
        "Okay. This has been getting worse over time.",
        "restored the non-emotional timeline content that had been dropped",
    ),
    (
        "pair_122",
        "ev_response",
        "You’re feeling increasingly worried and down. This has been getting worse over time.",
        "reduced stacked validation and kept the same substantive timeline as Control",
    ),
    (
        "pair_126",
        "ev_response",
        "You sound trusting. What did the strange machine do?",
        "removed an additional positive reaction",
    ),
    (
        "pair_130",
        "ev_response",
        "You sound hopeful. I hope this strategy works for you.",
        "removed stacked praise and reassurance",
    ),
    (
        "pair_131",
        "ev_response",
        "You’re feeling guilty and fearful. Whenever I have a large project and lose motivation, I set my goals on paper, then break it down into smaller bites. For example, I make sure I work one hour on certain days, call a friend, or generate ideas to keep me on track. The best thing to do is go to your advisor. She is the BEST person to go to, actually.",
        "restored advice force and matched substantive content to Control",
    ),
    (
        "pair_135",
        "ev_response",
        "It sounds like you feel overwhelmed. What is overwhelming you?",
        "removed stacked praise and validation",
    ),
    (
        "pair_136",
        "ev_response",
        "It sounds like you’re feeling really nervous. Have you been studying?",
        "removed a second general validation sentence",
    ),
    (
        "pair_137",
        "ev_response",
        "Your sadness and frustration are completely understandable. You’re very welcome!",
        "removed additional reassurance after the acknowledgement",
    ),
    (
        "pair_140",
        "ev_response",
        "You feel deeply distressed. It doesn’t really seem like your fault that you were there, but it is unfortunate nonetheless. Have you tried talking to him yet?",
        "removed a second explicit emotional restatement",
    ),
    (
        "pair_144",
        "ev_response",
        "You’re feeling worthless and inadequate. I apologize; I mean no disrespect.",
        "removed stacked reassurance so EV parallels Control",
    ),
    (
        "pair_145",
        "ev_response",
        "It sounds like you feel worried and uncertain. It always helps me to try to picture good possibilities and outcomes instead of bad ones. Is there any way you could imagine what kind of new things you could see in the near future that could help you get excited?",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_148",
        "ev_response",
        "You sound hopeful. Or just to be able to go into a store without a mask and hand sanitizer and constantly monitoring how close you are to people. When that day finally comes, we can finally start putting all of this behind us.",
        "removed emotional self-disclosure and extra reassurance",
    ),
    (
        "pair_157",
        "ev_response",
        "Your worry sounds understandable. If you worked in audio, some places, like Upwork and ACX (which does some audiobook work), are looking for audio editing. Other places may also be looking for audio editing. Fiverr may also be a good place to advertise audio work. I also have an Etsy and Ebay shop. You could possibly sell some of your carpentry work on there if that is possible. Ebay is free to list, and Etsy has a small listing fee.",
        "restored the original hypothetical tense and matched Control facts",
    ),
    (
        "pair_158",
        "ev_response",
        "You sound determined to quit. Nearly ten pounds per pack here in the UK. I’m gonna try saving up for a new handbag!",
        "replaced an ungrounded feeling with one expressed in context",
    ),
    (
        "pair_159",
        "ev_response",
        "You sound determined. You can and should get a job, so start right now!",
        "removed additional praise after the acknowledgement",
    ),
    (
        "pair_163",
        "ev_response",
        "I hear your frustration and overwhelm. My grandpa and my uncle died from Covid. You should be happy that you have them.",
        "removed stacked reaction and emotional self-disclosure while preserving facts",
    ),
    (
        "pair_165",
        "control_response",
        "Maybe before you talk to them, take some time to write down what you are feeling. You could even give them a letter to read if that makes you more comfortable.",
        "restored the original uncertainty and conditional advice force",
    ),
    (
        "pair_166",
        "control_response",
        "Do you think maybe menopause is making you more touchy?",
        "removed supporter's emotional self-disclosure",
    ),
    (
        "pair_166",
        "ev_response",
        "Your frustration sounds intense. Do you think maybe menopause is making you more touchy?",
        "removed imported context, extra validation, and emotional self-disclosure",
    ),
    (
        "pair_167",
        "ev_response",
        "Your frustration is understandable. Do you think she shares your concern, and if so, have you talked about it with her?",
        "removed a second restatement of frustration",
    ),
    (
        "pair_169",
        "ev_response",
        "Your hurt and frustration are completely understandable. Are you still together or have you left?",
        "removed validating endorsement of the stereotype so EV parallels Control",
    ),
    (
        "pair_174",
        "ev_response",
        "You sound worried. Mine are all out of state... the holidays will be hard.",
        "removed stacked normalization and extra emotional language",
    ),
    (
        "pair_176",
        "ev_response",
        "You’re feeling down, upset, and lonely. I don’t live with family anymore, so I haven’t seen my family for months either. I have a few things I’d like to share about how I’ve been getting through it. Maybe they will help you out :)",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_178",
        "control_response",
        "I pursued another degree. What would make you feel a bit more confident about the idea of school?",
        "removed supporter's emotional self-disclosure while preserving factual experience",
    ),
    (
        "pair_178",
        "ev_response",
        "Feeling apprehensive is completely understandable. I pursued another degree. What would make you feel a bit more confident about the idea of school?",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_183",
        "ev_response",
        "You seem worried. Surprisingly, a lot of parents do not get quality family time with their children.",
        "removed stacked reassurance so EV parallels Control",
    ),
    (
        "pair_190",
        "ev_response",
        "Your shame and anxiety sound overwhelming. The longer you keep drinking, the more damage you are doing to yourself.",
        "removed stacked reassurance and matched substantive content to Control",
    ),
    (
        "pair_191",
        "control_response",
        "I meditate, and it gives me relaxation and a new way to think. Sometimes our body and mind need peace to work better.",
        "removed supporter's emotional state while retaining advice from experience",
    ),
    (
        "pair_191",
        "ev_response",
        "You sound stressed and overwhelmed. I meditate, and it gives me relaxation and a new way to think. Sometimes our body and mind need peace to work better.",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_193",
        "ev_response",
        "You sound deeply depressed, lonely, and overwhelmed. I reached out for help like you are today, and I needed to start therapy.",
        "removed emotional self-disclosure after the acknowledgement",
    ),
    (
        "pair_200",
        "control_response",
        "You have had 5 or 6 bosses in 2 years. Do you work in a high-stress job?",
        "restored the dropped numbers and question without emotional validation",
    ),
    (
        "pair_200",
        "ev_response",
        "That sounds frustrating. You have had 5 or 6 bosses in 2 years. Do you work in a high-stress job?",
        "kept one acknowledgement and restored the concrete numbers and question",
    ),
]


def main() -> None:
    output = Path("work/corrections.csv")
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["example_id", "field", "corrected_text", "reason", "corrected_by"])
        for example_id, field, corrected_text, reason in CORRECTIONS:
            writer.writerow([example_id, field, corrected_text, reason, REVIEWER])
    print(f"Wrote {len(CORRECTIONS)} corrections to {output}")


if __name__ == "__main__":
    main()
