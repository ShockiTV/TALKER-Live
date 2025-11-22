# TALKER Expanded
A fork of [TALKER](https://github.com/danclave/TALKER). See the main repo for full installation instructions and setup guide.

This is my personal experiment attempting to get more immersion and roleplaying out of the already amazing TALKER mod, primarily by providing the LLM with more character and faction information but also delivering it through a revised prompt structure.

I am an absolute hack, and all credit for this amazing mod goes to the creators and maintainers of the main repo. Credit to [this](https://github.com/danclave/TALKER/issues/39) suggestion for forming the basis of the improved basic rules I'm using in my prompt. Credit to [issue#40](https://github.com/danclave/TALKER/issues/40) of the main repo for the basic code for reloading personalities on existing save games. Credit also to that same user again ([CanineHatTrickOnNose](https://github.com/CanineHatTrickOnNose)) for doing the initial revision of faction personalities and unique character personalities. I used his files as starting point, and some of his characterisations are still in the files wholesale alongside my additions as they fit the character well.

The majority of changes in this fork is just a bunch of writing to provide the LLMs with more information.

## CHANGES FROM MAIN BUILD

*   **Backstories:** The biggest change I've made is splitting personality into Traits and Backstories. Each unique character has unique traits, just like in base TALKER, but are now also provided with a unique backstory based on lore and information about the character in the game, from previous games and/or on the wiki. This should hopefully help the AI produce more immersive and lore-friendly responses, and let it refer to specific character details or backstory elements when appropriate, even unprompted. Each non-unique NPC is given a random backstory from a list of 50-70 depending on the faction. Monolith and Sin backstories are still WIP, and have only one placeholder each at this time.

*   **Expanded random NPC character personality:** In addition to revising and expanding the list of personality traits, the script has been modified to assign two random traits to every non-unique NPC instead of one. Between backstories and two traits, the hope is that every NPC will feel unique and distinctive.

*   **Increased faction description detail:** Faction descriptions fed to the LLM have been expanded, hopefully resulting in more detailed characterisation across faction members. NPCs should have better awareness of who they are and what they stand for.

*   **Immersion:** NPCs with specific roles (traders, technicians, medics, bartenders, guides etc) have their game function mentioned as part of the backstory. This should hopefully make responses be more immersive, such as bartenders offering you a drink even without you prompting them for it.

## EXISTING SAVES/RELOADING PERSONALITIES AND BACKGROUNDS
If you have an ongoing save, or you want to reset randomly generated personalities or backgrounds you can go to TALKER\bin\lua\domain\repo and in personalites.lua/backstories.lua you can change RESET_PERSONALITIES_ON_LOAD/RESET_BACKSTORIES_ON_LOAD from "false" to "true". After loading your save, save again. Then exit and change it back to "false". If you have non-unique companions you can reload multiple times until you get something you're happy with. You can see their personalities and backstory printed in the console after a reply, or just run the TALKER proxy with detailed logging.


## NOTES
I wanted a more fun, immersive experience for myself by trying to coax more distinctive and specific responses out of the AI by giving it more material to work with. Your mileage may vary. This expansion has not been tested at-length. I expect a lot of the backstories will need revision. Some backstories might be too prescriptive, leading to repetitive or monotone interactions if the NPC is your companion. More testing is needed.

Different LLMs will provide different output. This was tested on Google's Gemini-2.5-Flash and Nvidia's Kimi-K2-Instruct.

Gemini produces good and seemingly desired results, if occasionally somewhat boring. It takes instruction well, adheres to the rules and seems to understand how to use backstories to inform character behaviour.

Kimi-K2 produces better dialogue but is worse at adhering to instructions. The messages tend to be too long, and it insists on narrating or ``*emoting*`` what the character is doing despite being told not to. It also seems to generate more NPC-to-NPC conversations, which is sometimes good but sometimes bad.
