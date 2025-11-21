# TALKER Expanded
A fork of [https://github.com/danclave/TALKER](TALKER). Make sure to grab the latest verson of talker_mic.exe from the main repo.

See the main repo for full installation instructions and and setup guide.

This is my personal attempt at expanding on TALKER for improved immersion and roleplaying while using the mod during my ongoing playthrough. I do not claim to know what I'm doing.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo.

The majority of changes in this fork is just a bunch of writing to provide the LLMs with more information for character portrayal.

## CHANGES FROM MAIN BUILD

*   **Backstories** Added backstories as a component of character detail, in addition to personality. Every unique character has a custom backstory (WIP), consistent with lore and information about them in the game. Every non-unique character gets a random backstory selected from a list of 50-70 (depending on faction). Monolith and Sin have only one common backstory each across their respective faction at this time, reflecting their brainwashing. These factions are considered WIP at the moment and I might revise them if I can figure out how to write enough appropriate backstories for them.
*   **Expanded character personality:** The list of character traits has been revised and expanded. Every non-unique NPC now gets two randomly selected different traits instead of one. Every unique NPC has a custom, revised set of 3 character traits.
*   **Increased faction description detail:** Faction descriptions fed to the LLM have been expanded significantly, resulting - hopefully - in more detailed characterisation across faction members. NPCs should have better awareness of who they are and what they stand for.
*   **Immersion (WIP):** NPCs with specific roles (traders, technicians, medics, bartenders, guides etc) should be aware of their role and behave accordingly. Bartenders should offer you a drink, traders want to sell things. Guardposts at specific locations should behave accordingly.
*   **Revised prompt structure and general rules for the LLM:** Hopefully better output and character acting from the LLM.
*   **Fallback character profiles:** Unique characters that don't have a specified backstory or personality should get assigned a random backstory based on faction and a random personality.


## EXISTING SAVES/RELOADING PERSONALITIES AND BACKGROUNDS
If you have an ongoing save, or you want to reset randomly generated personalities or backgrounds you can go to TALKER\bin\lua\domain\repo and in personalites.lua/backstories.lua you can change RESET_PERSONALITIES_ON_LOAD/RESET_BACKSTORIES_ON_LOAD from "false" to "true". After loading your save, save again. Then exit and change it back to "false". If you have non-unique companions you can reload multiple times until you get something you're happy with.


## NOTES
Your mileage may vary. This expansion has not been tested at-length. I expect a lot of the backstories will need revision. Some backstories might be too prescriptive, leading to repetitive or monotone interactions if the NPC is your companion. More testing is needed.

Different LLMs will provide different output. This was tested on Google-Gemini-2.5-Flash and Nvidia/Kimi-K2-Instruct:

Gemini produces good and seemingly desired results, if occasionally somewhat boring.

Kimi-K2 produces better dialogue but is worse at adhering to instructions. The messages tend to be too long, and it insists on narrating or ``*emoting*`` what the character is doing despite being told not to.
