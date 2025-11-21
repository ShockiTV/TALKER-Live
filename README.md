# TALKER Expanded
A fork of [https://github.com/danclave/TALKER](TALKER). Make sure to grab the latest verson of talker_mic.exe from the main repo.

This is my personal attempt at improved immersion and roleplaying while using TALKER. See the main repo for full installation instructions and and setup guide.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo.

## Changes from main build

*   **Backstories** Backstories have been added as a component of character detail. Every unique character has a custom backstory (WIP), consistent with lore and information about them in the game. Every non-unique character gets a random backstory selected from a list of 50-70 (depending on faction). Monolith and Sin have only one common backstory each across their respective faction at this time, reflecting their brainwashing. These factions are considered WIP at the moment and I might revise them if I can figure out how to write enough appropriate backstories for them.
*   **Expanded character personality:** The list of character traits has been revised, as well as expanded from 63 traits to 93. Every non-unique NPC now gets two randomly selected different traits instead of one. Every unique NPC has a custom, revised set of 3 character traits.
*   **Increased faction description detail:** Faction descriptions fed to the LLM have been expanded significantly, resulting - hopefully - in more detailed characterisation across faction members. NPCs should have better awareness of who they are and what they stand for.
*   **Role-awareness:** NPCs with specific roles (traders, technicians, medics, bartenders, guides) are aware of their role and behave accordingly. Bartenders should offer you a drink, traders want to sell things.
*   **Revised prompt structure and general rules for the LLM:** Hopefully better output and character acting from the LLM.



## NOTES
Your mileage may vary. This expansion has not been tested at-length. I expect a lot of the backstories will need revision. Some backstories might be too prescriptive, leading to repetitive or monotone interactions if the NPC is your companion. More testing is needed.

Different LLMs will provide different output. This was tested on Google-Gemini-2.5-Flash and Nvidia/Kimi-K2-Instruct:

Gemini produces good and seemingly desired results, if occasionally somewhat boring.

Kimi-K2 produces better dialogue but is worse at adhering to instructions. The messages tend to be too long, and it insists on narrating or ``*emoting*`` what the character is doing despite being told not to.
