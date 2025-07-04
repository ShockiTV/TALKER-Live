# TALKER
A LLM powered dialogue generator for STALKER Anomaly

![TALKER](images/talker.png)

## notes
You no longer require openAI api credits to be able to use this mod! Changing the LLM model is possible, I left a door open for it at least in the code if anyone wants to give it a shot.

This mod is provided free of charge with open code, practice your own due diligence and set spending limits on your account. I have tested for bugs that could cause large amounts of requests but that does not mean it's impossible!

## Requirements
### LLM API Key Proxy
New provider (Free or paid, but made for free) now requires the use of the [LLM-API-Key-Proxy](https://github.com/Mirrowel/LLM-API-Key-Proxy). This proxy allows for rotating API keys, which helps to avoid rate-limiting issues and provides a more stable experience.

Please follow the instructions on the [LLM-API-Key-Proxy GitHub page](https://github.com/Mirrowel/LLM-API-Key-Proxy) to install and configure the proxy.

### talker_mic.exe
You must grab the `talker_mic.exe` from the [releases page](https://github.com/Mirrowel/TALKER/releases) and place it in the root folder of the mod.

## installation instructions
Best to use [Mod Organizer](https://lazystalker.blogspot.com/2020/11/mod-organizer-2-stalker-anomaly-setup.html)

### get an openapi key(if using openAI)
https://www.howtogeek.com/885918/how-to-get-an-openai-api-key/
put it in the openAi_API_KEY.key file as it was a text file

1.  **Install and configure the requirements listed above.**
2.  Place TALKER in a new mod folder, unpacked (For Gamma this is in E:\GAMMA\mods)
3.  Run `talker_mic.exe` and paste in your key(if asked).
4.  If it says everything's okay, keep it running and launch the game.
5.  You should be able to start speaking using the left alt key.

If you dont want to use the mic, you can still use the exe to add the key and then close it.

## Cheeki Breekivideo
- [![Cheeki Breeki](https://img.youtube.com/vi/WmM-PPKTA8s/0.jpg)](https://www.youtube.com/watch?v=WmM-PPKTA8s)

## using local models
1. install ollama
2. ollama pull llama3.2
3. ollama pull llama3.2:1b
4. ollama serve
5. run game and pick local models

## credits
Many thanks to
- [balls of pure diamond](https://www.youtube.com/@BallsOfPureDiamond), for making cool youtube videos and helping me brainstorm, playtest and stay hyped
- ThorsDecree for helping playtest
- [Cheeki Breeki](https://www.youtube.com/@CheekiBreekiTv)
- the many extremely helpful modders in the Anomaly discord
- Tosox
- RavenAscendant
- NLTP_ASHES
- Thial
- Lucy
- xcvb
- momopate
- Darkasleif
- Mirrowel
- Encrypterr
- lethrington
- Dunc
- Demonized
- Majorowsky
- beemanbp03
- abbihors, for boldly going where no stalker mod has gone before
- (Buckwheat in Russian) helping investigate pollnet
- many more who I rudely forgot
