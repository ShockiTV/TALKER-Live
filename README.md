# TALKER Expanded
A fork of [TALKER](https://github.com/danclave/TALKER). See the main repo for full installation instructions and setup guide.

This is my personal experiment attempting to get more immersion and roleplaying out of the already amazing TALKER mod.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo. Credit to [this](https://github.com/danclave/TALKER/issues/39) suggestion for forming the basis of the improved basic rules I'm using in my prompt. Credit to [issue#40](https://github.com/danclave/TALKER/issues/40) of the main repo for the basic code for reloading personalities on existing save games. Credit also to that same user again ([CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose)) for doing the initial revision of faction personalities and unique character personalities. I used his files as starting point, and some of his characterisations are still in the files wholesale alongside my additions as they fit the character well.

## CHANGES FROM MAIN BUILD

*   **Backstories:** The biggest fundamental change I've made is introducing Backstories. Each character now has a backstory to supplement their personality traits. Unique characters have unique backstories based on lore and information about the character in the game, from previous games and/or on the wiki. Each non-unique NPC is given a random backstory from a list of 100+ depending on the faction.

*  **Immersion:** NPCs with specific roles (traders, technicians, medics, bartenders, guides etc) have their game function mentioned as part of the backstory. This should hopefully make responses be more immersive, such as bartenders offering you a drink and guides acting like guides.

*   **Expanded random NPC character personality:** I have tried to revise the personality trait list, making sure the personality traits are interesting and lead to good output. I have also expanded the list from the default 63 to 144 entries (and counting), hopefully providing some more variety. Finally, the script now assigns *two* random personalitity traits to every NPC instead of one. I have found two personality traits to be the ideal number, as they can play off each other and combine into a distinct characterization without confusing the LLM. That combined with a random backstory will hopefully make every random NPC feel unique and distinctive.

*   **Better prompting:** The basic prompt has been greatly expanded, giving the LLM more information and more rules on how to behave. The goal is for every NPC to feel like a living person. The prompt generator has been revised as well to give more dynamic character information. NPCs should properly take their faction identity and rank into consideration, as well as that of whoever they're talking to.


## EXISTING SAVES/RELOADING PERSONALITIES AND BACKGROUNDS
If you have an ongoing save, or you want to reset randomly generated personalities or backstories you can go to TALKER\bin\lua\domain\repo and in personalites.lua/backstories.lua you can change RESET_PERSONALITIES_ON_LOAD/RESET_BACKSTORIES_ON_LOAD from "false" to "true". After loading your save, save again. Then exit and change it back to "false". If you have non-unique companions you can reload multiple times until you get something you're happy with. You can see their personalities and backstory printed in the console after a reply, or just run the TALKER proxy with detailed logging.


## NOTES
I have not tested my changes over a full playthrough. It's possible some backstories are too prescriptive and specific for NPCs that are your companions, leading to monotonous responses. Feedback and testing is needed.

Different LLMs will provide different output. This was tested on Google's Gemini-2.5-Flash and Nvidia's Kimi-K2-Instruct.

Gemini produces good results.

Kimi-K2 produces better dialogue but is worse at adhering to instructions. The messages tend to be too long, and it insists on narrating or ``*emoting*`` what the character is doing despite being told not to.
