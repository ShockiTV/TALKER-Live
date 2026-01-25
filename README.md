# TALKER Expanded
A fork of [TALKER](https://github.com/danclave/TALKER). See the main repo for full installation instructions and setup guide.

This is my personal experiment attempting to get more immersion and roleplaying out of the already amazing TALKER mod.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo. Credit to [this](https://github.com/danclave/TALKER/issues/39) and the discussion in that thread for setting me down on the road to fiddling with the prompt and learning amateur prompt engineering.

Credit to [CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose) for a lot of things to get the mod off the ground. They published their personal revisions of faction personalities and unique character personalities on the TALKER thread at the GAMMA Discord, which started me off on the path of tweaking these files even before I was fiddling with the prompt itself. Some remains of their characterisations are still in the files as they fit the character or faction well, and I want them to get credit for that.

I took their basic code for reloading personalities from [issue#40](https://github.com/danclave/TALKER/issues/40) of the main repo way back when I didn't even know how to vibe code yet.


## IMPORTANT:
*  **STALKER Anomaly must be launched DIRECTLY from the .EXE file in MO2 for TALKER Expanded to work properly.** Do NOT use the "Anomaly Launcher" to launch the game.

## FEATURES / CHANGES FROM REGULAR TALKER

*   **Full MCM Support:** Configure cooldowns, trigger distances, turn off dialogue triggers one-by-one and more, right in the MCM.

*   **Whispering:** Hold down a modifier key to talk ONLY to your companions. Their reply to your whisper will also only be heard by your companions. You can have private conversations with your companions wherever, even in crowded areas.
  
*   **Long-Term Memory:** TALKER Expanded uses a three-tier hierarchical memory system. The most recent up to 12 raw events are listed as is, the previous 12 events are summarized into a "mid-term memory", and each character has a limited but persistent long-term memory of up to 7000 characters. LLM calls are now used not just to compress events, but also to maintain long-term memory by periodically updating it with new information while removing older less relevant events. This gives the AI significantly increased context windows for their responses.

*   **Silent Events:** Most events can be toggled to "silent mode" in the MCM: this lets NPCs see and remember them happening without immediately commenting on them.

* **Better random NPCs:**
  -  **Backstories:** Is the random companion you picked up in Rostok on the run from the mob? Perhaps he's divorced and still can't get over his ex-wife, or he tried his luck in the Zone after being fired from the Railroad after being drunk on the job? Backstories are a new part of character identity that supplements the already existing personality, giving the LLM more information about characterization and making every NPC more unique and different from the next. Each random NPC is given a random backstory from a list of 100-200 options depending on the faction. Every faction has their own list, making sure they have their own unique flavour and have random faction NPCs end up with backstories that make sense for their faction identity. 
  -  **Expanded random NPC character personality:** I have tried to revise the personality trait list, making sure the personality traits are interesting and lead to good output. I have also expanded the list from the default 63 to over 200, hopefully providing some more variety. Several factions now also have faction-specific lists that add or remove entries as appropriate - it wouldn't make sense for an Ecolog to be "dumb as rocks" or "a moron" for example. Finally, the script now assigns *two* random personality traits to every NPC instead of one. I have found two personality traits to be the ideal number, as they can play off each other and combine into a distinct characterization without confusing the LLM. This - combined with a random backstory - will hopefully make every random NPC feel unique and distinctive.

* **Better unique NPCs:**
  - **Unique backstories:** Unique characters have unique backstories based on lore and information about the character in the game, from previous games and/or on the wiki. They should largely be aware of their past and their role.
  - **Unique personalities:** This was already a feature in base TALKER, but inspired by [CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose) each unique NPC now has a revised personality using 3-4 traits aiming to suit their personality in game.

*   **Faction/Rank/Reputation/Goodwill:** NPCs in TALKER Expanded are now aware of faction identity, ranks, reputation and goodwill - both their OWN and that of others. They will know if they are the same faction as you or not, and might treat you differently accordingly (ISG, Mercenaries and Duty treat their own faction members better than outsiders, for example). Rank and Reputation are both general behaviour modifiers and instructions on how to treat other: high/low rank people act differently and are treated differently. Same goes for good/bad reputation: it changes both how people act and how they are treated. NPCs know about your goodwill with their faction (and notable goodwill with other factions) and may treat you differently if you have very high or very low goodwill.

*   **Better location context:** Current location data in the prompt now pulls the name of the closest Smart Terrain, as well as whether you're next to a campfire or not and whether the fire is lit. NPCs are made aware of nearby characters in the prompt instead of having to guess based off of events. This allows for more contextual and immersive responses.

* **Dynamic world context:** NPCs are aware of whether the Brain Scorcher or Miracle Machine has been turned off, if Faction Leaders have died or if a section of other "important NPCs" (such as Beard, Arnie, Strelok, Butcher etc.) have died.   
  
* **Better prompting and immersion:** The prompt sent to the AI in TALKER is very basic. The LLM is given very little information to work with both in general, in relation to the speaking character and in relation to the surrounding world. The prompt in TALKER Expanded is greatly expanded and revised. The focus has been twofold: first on making NPCs feel more lifelike and more like independent people with their own lives and agendas. Second focus has been immersion and matching TALKER dialogue to consider important game information (such as reputation etc. listed above). NPCs that are your companions now know that they are companions, and behave a little more friendly towards you. NPCs with fixed roles like mechanics and bartenders are fed this information in the prompt so they can act naturally according to their role, offering you a drink or talking about repairs. In general the improved prompt and context should give more lifelike and immersive responses with most AI models.

* **LASS support:** Tick an MCM option checkbox if playing as a female gender protagonist to have NPCs adress you as female.

* **New Dialogue Triggers:** Completing tasks, sleeping and getting critically injured may now trigger dialogue events. Task and Sleep triggers are companion-aware: if you have companions they will know they also slept/comleted the task as a group.

* **Script fixes:** Idle Conversation and Artifact script now both work. Callout script has multiple anti-spam functions to ensure only valid new spotting events gets called out. Anomalies script filters out radioactive fields and radiation anomalies, preventing the behaviour in base TALKER of NPCs constantly talking about how irradiated you are and making jokes about you "glowing in the dark". Map Transition trigger is rewritten slightly to give more location information, and is now made companion-aware (your companions will remember they travelled with you as a group).

* **Improved Idle Conversation:** Idle conversation either causes a nearby NPC to ask the player a question, *or* picks a random discussion topic from talker_topics.xml (a leftover unimplemented file from Dan, the original TALKER creator). You can configure the percentage chance of asking a question in the MCM.  

* **Bug fixes:** Fixed several nil value errors, fixed several bugs related to the pick_speaker function.

* **Unfucked logging:** Default setting removes 90% of the incessant console log spamming TALKER does and delegates it to a debug logfile in TALKER/logs/talker_debug.log, which is wiped at the start of every session. In-game console (and thus Xray logs in appdata) only display *warnings* and *errors*.  

* **...and more**

## Mod Compatibility:
*  **KVMA Realism (Female characters):** I use KVMA Realism. Consequently, this mod treats the following characters as female: Kolin (mercenary tech in Zaton), Eidolon (monolith legend in Pripyat), Professor Semenov (Ecologist in Yantar). Edit these characters in unique_characters.lua/unique_backstories.lua if you don't want them characterized as female.
*  **New Levels** - Mostly compatible (AI training data will NOT include information about the new levels, but information *IS* provided by this mod when the map transition event triggers *as you enter* one of the new levels. NPCs will make accurate comments about the new levels when travelling to them, but might not if you randomly talk about Promzone while in Cordon and haven't been to Promzone yet, for example.)
*  **Arrival** - Theoretically compatible, not tested.
*  **Duty Expansion** - Fully compatible (Anna has a unique personality and backstory based on the mod)
*  **Western Goods** - Fully compatible (both traders have custom personalities and backstories)
*  **Perk-Based Artifacts** - Mostly compatible (Same scenario as New Levels: artifact triggers include information about the perk of the picked up/equipped artifact. NPCs will make accurate comments when you interact with a Perk-Based Artifact, but ask them out of context what a 'Bat' does and they will hallucinate.)

## EXISTING SAVES/RESETTING PERSONALITIES AND BACKSTORIES
* TALKER Expanded can be installed on an ongoing save without issues, whether you have played with base TALKER before or not.
* **IF** you have used base TALKER before, Expanded has a built-in function to migrate the base TALKER event system into the new hierarchical long-term memory system.
   - The first time you talk to somebody, an LLM call is made that generates a summarized long-term memory for that character out of the entire list of raw events they have witnessed so far. If you have a companion, they might suddenly remember old events that happened a long time ago.
   - You can use the "reset personalities" function in the MCM to update existing NPCs to use the expanded personality system in Expanded.
* To reset personalities or backstories, simply tick the checkbox in the MCM and load your save. After loading in, untick the checkbox, save, and keep playing as normal.
   - IF you have a companion, you can reload multiple times to reroll personality/backstory for your companion until you get something you're happy with. Check the debug logs in TALKER/logs/talker_debug.log to see the exact backstory and personality of your companion (and anyone else involved in events).


## NOTES ON LLMs
* **Tested models for dialogue:**
   - **iflow/deepseek-v3.2**: Good, balanced model that gives solid responses while being fast enough. Follows instructions well, doesn't do anything extravagant and generates good and grounded responses. Iflow has generous rate limits and you can get API keys simply by registering with burner Google accounts, while this model is also available all the time and producing fast replies. The whole package makes this model easy to recommend for most users.
      -  **WARNING:** iflow does not support concurrent calls, but TALKER Expanded (and even base TALKER) can regularly create situation where multiple parrallel calls are made at once. You should register *several* accounts on iflow to safeguard against this. Luckily it's as easy as creating multiple burner Google accounts. I have 4 accounts currently, which has proven to be sufficient even when using iflow for both dialogue and non-dialogue.
   - **nvidia_nim/moonshotai/kimi-k2-instruct-0905**: Produces great dialogue with livelier and more elaborate prose than iflow/deepseek-v3.2, but is poor at following instructions closely.  More recent revisions of the prompt seem to have succesfully reigned it in a bit and I now consider it usable and would recommend it. I have used it a lot as I enjoy the way it writes, but it has a slightly "extravagant" or poetic slant that some users don't enjoy. **WARNING:** This model has started to become unavailable more often, though it seems to vary highly from day to day and even time of day. Might not provide usable response times at all times anymore.
   - **nvidia_nim/moonshotai/kimi-k2-instruct**: A slightly older version of the model above. Same general description applies. If you like 0905 but it is unavailable or slow, you can use this model instead as it is pretty much always available and giving fast responses.
   - **nvidia_nim/mistralai/mistral-large-3-675b-instruct-2512**: *GREAT* model for dialogue... when it's available. This would be my go-to recommendation, but it is sadly very often overloaded/unavailable/too slow these days. You can try it out and see what your response times are, they seem to vary wildly based on time of day/day of the week. I used it for a while just fine but lately it seems like the response times are getting worse and worse. You will very often see response times at over a minute nowadays - way out of gamplay usage range.
   - **nvidia_nim/qwen/qwen3-next-80b-a3b-instruct**: Fast model that is almost always available and produces okay dialogue. It's a little boring, and not ideal for dialogue in my opinion, but it's a usable and fast Nvidia model that is less extravagant than Kimi-K2. Worth trying if you want something more subdued and than Kimi, but don't want to use iflow for whatever reason.
   - **gemini/gemini-2.5-flash**: Great model, fast despite being a thinking model and follows the prompt instructions well. Will produce good results if you for some reason want to pay Google for higher rate limits, but does not in my opinion produce meaningfully better dialogue than the free options to be worth paying for. If you happen to have like 10 valid and verified Google accounts lying around you could create 12 API keys for each and still use this for free, which in that case sure, go for it.
      - **WARNING:** For emphasis I will repeat that you need **MANY MANY** accounts to be able to use this model for gameplay for free. You probably need over 50 API keys to reliably use Gemini for free if you play for any length of time in a day. Even more than that if you use Gemini to transcribe your microphone audio. Even if you have a couple of valid Google accounts available, I recommend using those API keys for *microphone audio transcription* (Gemini is much more accurate than Whisper) and use *another free model* for dialogue.
 
### BAD MODELS (DO NOT USE)
   - **iflow/kimi-k2:** Produces weird and overtly hostile dialogue. AVOID - use iflow/deepseek-v3.2 instead if you're using iflow.
   - **nvidia_nim/qwen/qwen3-next-80b-a3b-thinking**: Thinking version of the qwen3 model above, which produces much better dialogue. Surprisingly fast for a thinking non-Gemini model, ALMOST to the point of usability. Produces great results, but is often too slow/overloaded/unavailable. You may try it, but realistically probably produces too big response delays for gameplay use.
   - **nvidia_nim/moonshotai/kimi-k2-thinking**: WAY too slow for gameplay use. Unfortunate as it produces great dialogue and is much better at following instructions than non-thinking kimi-k2.

### Non-dialogue
* **"Fast" model for non-dialogue is VERY important:** This model is responsible for memory management, and thus is directly responsible for how well each character's long-term memory functions. The model needs to understand memory management prompts well in order to correctly summarize essential information while discarding irrelevant events and memories. However, it also needs to be *fast*, as it is responsible for the function that picks the speaker of an event (and you also don't want memory management to take too long, as otherwise you create gaps in characterization).
* **iflow/deepseek-v3.2:** Fast *enough* to use as a fast model, while still being very good at memory management. This is my recommended model for non-dialogue.
* **nvidia_nim/qwen/qwen3-next-80b-a3b-instruct** Second-best of the ones I've tested. Use this model for non-dialogue if you don't want to use Iflow models. It is fast, takes instruction well and good at editing the memory text.

### Dubious models for non-dialogue (not recommended)
* **gemini/gemini-2.5-flash-lite:** Struggles with memory management. It is fast enough, and should be "usable" if you really want it to, but sometimes produces malformed output for long-term memory. There is no reason to use this for non-dialogue, in my opinion, even if you want to pay Google to use Gemini for dialogue (which you might, it still is a great model for that).
* **nvidia_nim/moonshotai/kimi-k2-instruct**
* 
