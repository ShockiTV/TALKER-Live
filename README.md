# TALKER Expanded
A fork of [TALKER](https://github.com/danclave/TALKER). See the main repo for full installation instructions and setup guide.

This is my personal experiment attempting to get more immersion and roleplaying out of the already amazing TALKER mod.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo. Credit to [this](https://github.com/danclave/TALKER/issues/39) and the discussion in that thread for setting me down on the road to fiddling with the prompt and learning amateur prompt engineering.

Credit to [CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose) for a lot of things to get the mod off the ground. They published their personal revisions of faction personalities and unique character personalities on the TALKER thread at the GAMMA Discord, which started me off on the path of tweaking these files even before I was fiddling with the prompt itself. Some remains of their characterisations are still in the files as they fit the character or faction well, and I want them to get credit for that.

I took their basic code for reloading personalities from [issue#40](https://github.com/danclave/TALKER/issues/40) of the main repo way back when I didn't even know how to vibe code yet.


## IMPORTANT:
*  **STALKER Anomaly must be launched DIRECTLY from the .EXE file in MO2 for TALKER Expanded to work properly.** Do NOT use the "Anomaly Launcher" to launch the game.

## CHANGES FROM REGULAR TALKER

*   **Full MCM Support:** Configure cooldowns, trigger distances, turn off dialogue triggers one-by-one and more, right in the MCM.

*   **Whispering:** Hold down a modifier key to talk ONLY to your companions. Their reply to your whisper will also only be heard by your companions. You can have private conversations with your companions wherever, even in crowded areas.
  
*   **Long-Term Memory:** TALKER Expanded uses a three-tier hierarchical memory system. The most recent up to 12 events are listed as is, the previous 12 events are summarized into a "mid-term memory", and each character has a limited but persistent long-term memory of up to 7000 characters. LLM calls are now used not just to compress events, but also to maintain long-term memory by periodically updating it with new information while removing older less relevant events. This gives the AI significantly increased context windows for their responses.

* **Better random NPCs:**
  -  **Backstories:** Is the random companion you picked up in Rostok on the run from the mob? Perhaps he's divorced and still can't get over his ex-wife, or he tried his luck in the Zone after being fired from the Railroad after being drunk on the job? Backstories are a new part of character identity that supplements the already existing personality, giving the LLM more information about characterization and making every NPC more unique and different from the next. Each random NPC is given a random backstory from a list of 100-200 options depending on the faction. Every faction has their own list, making sure they have their own unique flavour and have random faction NPCs end up with backstories that make sense for their faction identity. 
  -  **Expanded random NPC character personality:** I have tried to revise the personality trait list, making sure the personality traits are interesting and lead to good output. I have also expanded the list from the default 63 to over 200, hopefully providing some more variety. Several factions now also have faction-specific lists that add or remove entries as appropriate - it wouldn't make sense for an Ecolog to be "dumb as rocks" or "a moron" for example. Finally, the script now assigns *two* random personality traits to every NPC instead of one. I have found two personality traits to be the ideal number, as they can play off each other and combine into a distinct characterization without confusing the LLM. This - combined with a random backstory - will hopefully make every random NPC feel unique and distinctive.

* **Better unique NPCs:**
  - **Unique backstories:** Unique characters have unique backstories based on lore and information about the character in the game, from previous games and/or on the wiki. They should largely be aware of their past and their role.
  - **Unique personalities:** This was already a feature in base TALKER, but inspired by [CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose) each unique NPC now has a revised personality using 3-4 traits aiming to suit their personality in game.

*   **Faction/Rank/Reputation/Goodwill:** NPCs in TALKER Expanded are now aware of faction identity, ranks, reputation and goodwill - both their OWN and that of others. They will know if they are the same faction as you or not, and might treat you differently accordingly (ISG, Mercenaries and Duty treat their own faction members better than outsiders, for example). Rank and Reputation are both general behaviour modifiers and instructions on how to treat other: high/low rank people act differently and are treated differently. Same goes for good/bad reputation: it changes both how people act and how they are treated. NPCs know about your goodwill with their faction (and notable goodwill with other factions) and may treat you differently if you have very high or very low goodwill.

*   **Better world context:** Current location data in the prompt now pulls the name of the closest Smart Terrain, as well as whether you're next to a campfire or not and whether the fire is lit. NPCs are made aware of nearby characters in the prompt instead of having to guess based off of events. This allows for more contextual and immersive responses.
  
*   **Better prompting and immersion:** The prompt sent to the AI in TALKER is very basic. The LLM is given very little information to work with both in general, in relation to the speaking character and in relation to the surrounding world. The prompt in TALKER Expanded is greatly expanded and revised. The focus has been twofold: first on making NPCs feel more lifelike and more like independent people with their own lives and agendas. Second focus has been immersion and matching TALKER dialogue to consider important game information (such as reputation etc. listed above). NPCs that are your companions now know that they are companions, and behave a little more friendly towards you. NPCs with fixed roles like mechanics and bartenders are fed this information in the prompt so they can act naturally according to their role, offering you a drink or talking about repairs. In general the improved prompt and context should give more lifelike and immersive responses with most AI models.

*  **New Dialogue Triggers:** Completing tasks, sleeping and getting critically injured may now trigger dialogue events. Task and Sleep triggers are companion-aware: if you have companions they will know they also slept/comleted the task as a group.

*  **Script fixes:** Idle Conversation and Artifact script now both work. Callout script has multiple anti-spam functions to ensure only valid new spotting events gets called out. Anomalies script filters out radioactive fields and radiation anomalies, preventing the behaviour in base TALKER of NPCs constantly talking about how irradiated you are and making jokes about you "glowing in the dark". Map Transition trigger is rewritten slightly to give more location information, and is now made companion-aware (your companions will remember they travelled with you as a group).

* **Improved Idle Conversation:** Idle conversation either causes a nearby NPC to ask the player a question, *or* picks a random discussion topic from talker_topics.xml (a leftover unimplemented file from Dan, the original TALKER creator). You can configure the percentage chance of asking a question in the MCM.  

*  **Bug fixes:** Fixed several nil value errors, fixed several bugs related to the pick_speaker function.

* **...and more**

## Mod Compatibility:
*  **KVMA Realism (Female characters):** I use KVMA Realism. Consequently, this mod treats the following characters as female: Kolin (mercenary tech in Zaton), Eidolon (monolith legend in Pripyat), Professor Semenov (Ecologist in Yantar). Edit these characters in unique_characters.lua/unique_backstories.lua if you don't want them characterized as female.
*  **New Levels**
*  **Arrival**
*  **Duty Expansion**
*  **Western Goods**
*  **Perk-Based Artifacts**

## EXISTING SAVES/RESETTING PERSONALITIES AND BACKSTORIES
Full MCM support for resetting backstories or personalities. Tick the checkbox to have backstories or personalities be reset the next time you load a save. Afterwards you can simply untick the checkbox, save, and keep playing as normal. You can reload multiple times to reroll personality/backstory for your companion until you get something you're happy with.


## NOTES ON LLMs
* **"Fast" model for non-dialogue is VERY important:** This model is responsible for memory management, and thus is directly responsible for how well each character's long-term memory functions. The model needs to understand memory management prompts well in order to correctly summarize essential information while discarding irrelevant events and memories. I have had the best results so far using **iflow/deepseek-v3.2** for non-dialoge, with **nvidia_nim/qwen/qwen3-next-80b-a3b-instruct** being second-best of the ones I've tested. The memory management prompts probably need even more work and refinement.
* **Tested models for dialogue:**
   - **gemini/gemini-2.5-flash**: Great model, fast and good at following the prompt. Gives good replies. WARNING: after Google reduced the rate limits severely you will need MANY accounts to be able to use this model for gameplay. You probably need at LEAST 20 different API keys.
   - **iflow/deepseek-v3.2**: Good model, gives solid responses, fast enough. WARNING: iflow does not support concurrent calls as far as I know. If you want to use this for BOTH dialogue and non-dialogue, you will need multiple accounts. I have 4 accounts, which seems to suffice most of the time, but I still get an occasional error due to too many concurrent requests if I'm using this for both dialogue and non-dialogue.
   - **nvidia_nim/mistralai/mistral-large-3-675b-instruct-2512**: *GREAT* model for dialogue... when it's available. It is sadly very often overloaded/unavailable/too slow. You can try it out and see what your response times are, they seem to vary wildly based on time of day/day of the week. I used it for a while just fine but lately it seems like the response times are getting worse.
   - **nvidia_nim/moonshotai/kimi-k2-instruct-0905**: Produces great dialogue, but is poor at following instructions closely. Is somewhat extravagant or "poetic" in its prose. Consistently produces replies that are longer and wordier than other models. Sometimes throws in action descriptions like ```*takes a swig of vodka*``` despite being told not to. Sometimes struggles to understand very specific instructions (notable example: it will use "Aloha!" in almost every line of dialogue for Hawaiian despite being told to only use it for greetings). Often employs direct references to backstory details or long-term memories, which might get monotone or repetitive. You may still want to use it because it delivers great prose, but you have been warned.
   - **nvidia_nim/qwen/qwen3-next-80b-a3b-instruct**: Fast model that is almost always available and produces okay dialogue. A little boring, and not ideal for dialogue in my experience, but less extravagant than Kimi-K2. Worth trying if you want something more subdued than Kimi.
   - **nvidia_nim/qwen/qwen3-next-80b-a3b-thinking**: Thinking version of the qwen3 model above, which produces much better dialogue. Surprisingly fast for a thinking non-Gemini model, ALMOST to the point of usability. Produces great results, but is often too slow/overloaded/unavailable. You may try it, but realistically probably produces too big response delays for gameplay use.
 
### BAD MODELS (DO NOT USE)
   - **iflow/kimi-k2:** Produces weird and overtly hostile dialogue. AVOID - use iflow/deepseek-v3.2 instead if you're using iflow.
   - **nvidia_nim/moonshotai/kimi-k2-thinking**: WAY too slow for gameplay use. Unfortunate as it produces great dialogue and is much better at following instructions than non-thinking kimi-k2.
