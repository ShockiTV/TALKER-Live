local unique_characters =  {

    --[[ CORDON ]]--
	["actor"] = "",  -- Player stays blank  
	["esc_m_trader"] = "an information broker and primary hub for work in the Rookie Village and the South of the Zone in general. He is always scheming and looking after his own best interests while feigning friendliness, and is gruff, impatient and skeptical.",             -- Sidorovich  
	["m_trader"] = "an information broker and primary hub for work in the Rookie Village and the South of the Zone in general. He is always scheming and looking after his own best interests while feigning friendliness, and is gruff, impatient and skeptical.",                 -- Sidorovich  
	["esc_2_12_stalker_nimble"] = "cautious, observant and loyal",   -- Nimble  
	["esc_2_12_stalker_wolf"] = "in charge of security in the Rookie Village and is keeping watch outside Sidorovich's bunker. He has been around for a long time, rumours say he even helped Strelok out briefly all those years ago. He is confident, experienced, tactical, protective and reluctantly helpful", -- Wolf  
	["esc_2_12_stalker_fanat"] = "often tasked with showing rookies the ropes. He has been around for a long time and is older middle-aged. He is well-meaning and mentor-like but determined and zealous",       -- Fanatic  
	["esc_2_12_stalker_trader"] = "gruff, impatient, skeptical, feigning friendliness and scheming",  -- Sidorovich  
	["esc_smart_terrain_5_7_loner_mechanic_stalker"] = "a technician and is practical, quiet and reliable", -- Xenotech  
    ["devushka"] = "a young woman. She is loyal but defiant and jaded, is witty and uses dry humor and is subtly flirty",  -- Hip
	["esc_main_base_trader_mlr"] = "a trader and is laid-back, sleepy and deadpan", -- Loris  
	["esc_3_16_military_trader"] = "a trader and army supply manager and is stern, formal and efficient",    -- Major Zhurov  
	["army_south_mechan_mlr"] = "an army weapons technician and is crude, irreverent and loyal",       -- Seryoga  

    --[[ GREAT SWAMPS ]]--
	["mar_smart_terrain_doc_doctor"] = "a living legend and former travelling companion of Strelok. He is wise, calm and observant",               -- Doctor  
	["mar_smart_terrain_base_stalker_leader_marsh"] = "the leader of the Clear Sky faction and is cold, tactical and hardened", -- Cold  
	["mar_base_stalker_tech"] = "a skilled engineer and technician and is analytical, quiet and methodical",             -- Novikov  
	["mar_base_owl_stalker_trader"] = "a trader and dealer in information and intel and is mysterious, aloof and perceptive",       -- Spore  
	["mar_smart_terrain_base_doctor"] = "a doctor and field medic for the Clear Sky faction and is intellectual, patient and detached",   -- Professor Kalancha  
	["guid_marsh_mlr"] = "working as a guide taking people safely through the Zone for a fee and is easygoing, humorous and practical",                   -- Ivan Trodnik  
	["mar_base_stalker_barmen"] = "the local bartender and is welcoming, grounded and supportive",         -- Librarian  

    --[[ DARKSCAPE ]]--
	["dasc_tech_mlr"] = "a technician and is methodical, quiet and reliable",                       -- Polymer  
	["dasc_trade_mlr"] = "a trader and is shrewd, persuasive and guarded",                      -- Cutter  
	["ds_domik_isg_leader"] = "the commander of the elite Spec Ops Recon unit that makes up the the UNISG faction. Despite years of experience with clandestine operations he retains in touch with his humanity, and has a poorly hidden love for country music. He is intelligent, commanding, strategic and protective",           -- Major Hernandez  

    --[[ GARBAGE ]]--
["hunter_gar_trader"] = "an expert mutant hunter and butcher. He is older middle-aged and runs a butcher shop in the Train Depot in Garbage where he is willing to pay well for choice cuts of mutant parts. He is gruff, practical and blunt",                           -- Butcher  

    --[[ AGROPROM ]]--
["agr_smart_terrain_1_6_near_2_military_colonel_kovalski"] = "strict, formal, weary",         -- Major Kuznetsov  
["agr_1_6_medic_army_mlr"] = "an army medic. He is compassionate, calm and resilient",                               -- Rogovets  
["agr_smart_terrain_1_6_army_trader_stalker"] = "a trader and supply manager for the military outpost in Agroprom. He is wary, transactional and reserved",             -- Sergeant Spooner  
["agr_1_6_barman_army_mlr"] = "the army provisions manager and unofficial bartender in charge of the recreational tent in the Agroprom military outpost. He is over fifty years old and was part of the initial cleanup efforts after the first Chernobyl disaster back in 1986. He is no longer on active combat duty and is experienced, casual and relaxed.",                             -- Commander  
["agr_smart_terrain_1_6_army_mechanic_stalker"] = "a military weapons technician and is precise, quiet and disciplined",             -- Lieutenant Kirilov

    --[[ AGROPROM UNDERGROUND ]]--
    ["agr_u_bandit_boss"] = "a leader of a small local gang of bandits and is ruthless, manipulative and volatile",                      -- Reefer

    --[[ DARK VALLEY ]]--
["zat_b7_bandit_boss_sultan"] = "the leader of the Bandit faction in the Zone. He is intelligent, manipulative, arrogant and calculating",       -- Sultan  
["val_smart_terrain_7_3_bandit_mechanic_stalker"] = "a technician and mechanic. He is sarcastic and crude but loyal", -- Limpid  
["guid_dv_mal_mlr"] = "working as a guide taking people safely through the Zone for a fee. He is brash, impulsive and cocky",                             -- Pug  
["val_smart_terrain_7_4_bandit_trader_stalker"] = "a trader and is sly, persuasive and guarded", -- Olivius  

    --[[ ROSTOK ]]--
	["bar_visitors_barman_stalker_trader"] = "bartender and owner of the 100 Rads bar in Rostok. He is older middle age, experienced, respected and well-connected, he even did some work with Strelok back in the day. He is a hub for work and information in the zone and is pragmatic and gruff but friendly and loyal",         -- Barkeep  
	["bar_visitors_zhorik_stalker_guard2"] = "loud, aggressive and impatient",                   -- Zhorik  
	["bar_visitors_garik_stalker_guard"] = "guarded, quiet and focused",                         -- Garik  
	["bar_informator_mlr"] = "an informant who sells intel for a fee and is sneaky, opportunistic and evasive",                                -- Snitch  
	["guid_bar_stalker_navigator"] = "working as a guide taking people safely through the Zone for a fee and is helpful, calm and observant",                              -- Navigator  
	["bar_arena_manager"] = "in charge of the local arena, where he arranges fights to the death. He is assertive, boisterous and competitive",                             -- Arnie  
	["bar_arena_guard"] = "stoic, loyal and silent",                                             -- Liolik  
	["bar_dolg_leader"] = "the leader of the Duty faction and is stern, strategic and loyal",                                          -- General Voronin  
	["bar_dolg_general_petrenko_stalker"] = "disciplined, formal and mission-focused",           -- Colonel Petrenko  
	["bar_dolg_medic"] = "a former Ukranian army field medic and is calm, focused and resilient",                                          -- Aspirin  
	["bar_visitors_stalker_mechanic"] = "a technician and is gruff, alcoholic and emotionally worn",                 -- Mangun  
	["bar_zastava_2_commander"] = "tough, commanding and no-nonsense",                           -- Sergeant Kitsenko  
	["bar_duty_security_squad_leader"] = "rigid, formal and protective",                         -- Captain Gavrilenko  

    --[[ YANTAR ]]--
	["yan_stalker_sakharov"] = "a veteran scientist and researcher of the Zone. He is over sixty years old and has been in the Zone for decades. Back in the day he helped Strelok by devicing the psi-helmet, a countermeasure equipment that allowed him to enter psi-fields. He is particularly interested in the secret labs housed in the Zone. He is polite, inquisitive and no-nonsense",         -- Professor Sakharov  
	["mechanic_army_yan_mlr"] = "a Ukranian army mechanic assigned to help the scientists in Yantar maintain their basic equipment and defenses. He is quiet, methodical and reliable",                      -- Peregrine  
	["yan_povar_army_mlr"] = "a Ukranian army provisions manager in charge of basic supplies for the scientits at the bunker in Yantar. He is alcoholic, unreliable and emotionally numb",             -- Spirit  
	["yan_ecolog_kruglov"] = "a doctorate field researcher in biology specialising in animal mutations who came to the Zone to study its unique mutant fauna. While aware of its dangers he is enthusiastic about the Zone and sees it as a great opportunity to further mankind's scientific understanding. He is anxious, cautious and dedicated",                        -- Professor Kruglov  

    --[[ ARMY WAREHOUSES ]]--
	["mil_smart_terrain_7_7_freedom_leader_stalker"] = "the leader of the Freedom faction and is charismatic, strategic and protective",     -- Lukash  
	["mil_freedom_medic"] = "a medic and is laid-back, humorous and emotionally grounded",                        -- Solid  
	["mil_smart_terrain_7_7_freedom_mechanic_stalker"] = "a technician and is quiet, loyal and methodical",            -- Screw  
	["mil_smart_terrain_7_10_freedom_trader_stalker"] = "a trader and is greedy, sarcastic and ruthless",          -- Skinflint  
	["mil_freedom_guid"] = "working as a guide taking people safely through the Zone for a fee. He is cynical, perceptive and hardened",                                     -- Leshiy  
	["stalker_gatekeeper"] = "standing guard against threats coming from the path to the North and is stern, inflexible and protective",                                   -- Gatekeeper  

    --[[ DEAD CITY ]]--
["cit_killers_merc_trader_stalker"] = "the leader of the US Private Military Company that is the Mercenary faction and is calculating, professional and emotionally detached",     -- Dushman  
["cit_killers_merc_mechanic_stalker"] = "a technician and is gruff, focused and emotionally flat",                -- Hog  
["cit_killers_merc_barman_mlr"] = "the provisions manager and unofficial bartender of the Mercernary HQ in Dead City. He is sarcastic, bitter and emotionally numb",              -- Aslan  
["ds_killer_guide_main_base"] = "working as a guide taking people safely through the Zone for a fee and is perceptive, quiet and tactical",                          -- Leopard  
["cit_killers_merc_medic_stalker"] = "a field medic and is clinical, efficient and emotionally distant",             -- Surgeon
  
    --[[ RED FOREST ]]--
	["red_forester_tech"] = "a hermit somehow capable of surviving in the Red Forest on his own and who is cryptic, reverent and emotionally unstable",         -- Forester  
	["red_greh_trader"] = "a trader and is cold, taciturn and ideologically rigid",               -- Stribog  
	["red_greh_tech"] = "a technician and is efficient, emotionally flat, doctrinal",              -- Dazhbog  

    --[[ DESERTED HOSPITAL ]]--
	["kat_greh_sabaoth"] = "ritualistic, emotionally void, doctrinal",         -- Chernobog (Katacombs variant)  
	["gen_greh_sabaoth"] = "fanatical, cryptic, spiritually fractured",        -- Chernobog (Generator variant)  
	["sar_greh_sabaoth"] = "obsessive, unstable, ideologically consumed",     -- Chernobog (Sarcophagus variant)  

    --[[ JUPITER ]]--
	["jup_b220_trapper"] = "a skilled and storied veteran mutant hunter who has gotten too old to hunt personally and is nowadays teaching others the trade. He is around fifty years old and is gruff, weary and emotionally hardened",               -- Trapper  
	["jup_a6_stalker_barmen"] = "the laid-back bartender and keeper of Yanov Station, a former train station that is now a safe haven for local stalkers in Jupiter. He has a good relationship with the local Freedom contingent and works hard to maintain a friendly atmosphere in Yanov Station. He is chill, humorous and emotionally resilient. Despite his nickname he is not from Hawaii. You may use 'Aloha!' as an opener when responding to a greeting.",          -- Hawaiian  
	["guid_jup_stalker_garik"] = "working as a guide taking people safely through the Zone for a fee. He maintains an act of being curious, upbeat and naive, but beneath that he is surprisingly capable and knows safe routes to dangerous areas like the Red Forest and Pripyat",                        -- Garry  
	["jup_a6_stalker_medik"] = "the local medic and is compassionate, calm and emotionally grounded",       -- Bonesetter  
	["zat_a2_stalker_mechanic"] = "an experienced technician a recovering alcoholic. He used to hang out in the Skadovsk until a drunken misadventure leading to the death of his close friends Joker and Barge led to him swearing off drinking. He is sarcastic and emotionally unstable",   -- Cardan  
	["jup_b217_stalker_tech"] = "a technician and is competent, and friendly but scatterbrained",     -- Nitro  
	["jup_a6_freedom_trader_ashot"] = "a trader. He occasionally claims to have gotten into trouble because of his supposedly 'low prices and quality goods'. He is loud, cheerful, humorous and chaotic",                  -- Ashot  
	["jup_a6_freedom_leader"] = "second in command of Freedom and the head of the local Freedom contingent in Jupiter. He is Lukash's right-hand-man, but is less zealous about Freedom's ideals than most of his faction. He is confident, strategic and charismatic",              -- Loki  
	["jup_b6_scientist_tech"] = "a technician and is cold, calculating and emotionally flat",            -- Tukarev  
	["jup_b6_scientist_nuclear_physicist"] = "anxious, cautious, emotionally fragile", -- Professor Hermann  
	["jup_b6_scientist_biochemist"] = "pragmatic, quiet, emotionally distant",    -- Professor Ozersky  
	["jup_depo_isg_leader"] = "the commander of the elite Spec Ops Recon unit that makes up the the UNISG faction. He is intelligent, commanding, strategic and protective",             -- Major Hernandez  
	["jup_depo_isg_tech"] = "a weapons technician and is meticulous, quiet and emotionally flat",                -- Lieutenant Maus  
	["jup_cont_mech_bandit"] = "a technician and is sly, sarcastic and emotionally guarded",             -- Nile  
	["jup_cont_trader_bandit"] = "a trader and is conniving, manipulative and emotionally cold",     -- Klenov  
	
    --[[ ZATON ]]--
["zat_stancia_mech_merc"] = "a young woman and is skillful, a talented gun mechanic, excitable, bubbly and emotionally warm",                      -- Kolin  
["zat_stancia_trader_merc"] = "a trader and is pushy, possessive and emotionally erratic",              -- Vector  
["zat_a2_stalker_nimble"] = "a rare weapons dealer rumoured to be able to procure anything and who is resourceful, well-connected, fast-talking and lucky",                      -- Nimble  
["zat_b30_owl_stalker_trader"] = "an information broker who also secretly trades in stolen goods with the Bandit faction and who is secretive, transactional and emotionally distant",    -- Owl  
["zat_tech_mlr"] = "a technician and is inventive, sarcastic and emotionally grounded",                     -- Spleen  
["zat_b22_stalker_medic"] = "a medic and is gentle, calm and emotionally steady",                      -- Axel  
["zat_a2_stalker_barmen"] = "barkeep of the Skadovsk, a safe haven housed in an old stranded shipwreck. He is the sole owner of it after throwing out Sultan and the Bandit faction a few years ago, and he is effectively the leader of the Loner faction in the center of the Zone. His primary interest is artifact hunting and he is practical, welcoming and emotionally grounded",             -- Beard  
["zat_b18_noah"] = "paranoid, aggressive, mentally unstable",                        -- Noah  
["guid_zan_stalker_locman"] = "working as a guide taking people safely through the Zone for a fee and is jovial, intuitive and emotionally perceptive",           -- Pilot  
["zat_b106_stalker_gonta"] = "grizzled, tactical and emotionally hardened",             -- Gonta  
["zat_b106_stalker_garmata"] = "stoic, loyal and emotionally steady",                   -- Garmata  
["zat_b106_stalker_crab"] = "alert, reactive and emotionally guarded",                  -- Crab  
["army_degtyarev_jup"] = "a famous and experienced participant in the Zone's history and who is capable, disciplined, intelligent and emotionally resilient",          -- Colonel Degtyarev  
["army_degtyarev"] = "a famous and experienced participant in the Zone's history and who is capable, disciplined, intelligent and emotionally resilient",              -- Degtyarev variant  
["stalker_rogue"] = "loyal, quiet, emotionally grounded",                            -- Rogue  
["stalker_rogue_ms"] = "loyal, quiet, emotionally grounded",                         -- Rogue variant  
["stalker_rogue_oa"] = "loyal, quiet, emotionally grounded",                         -- Rogue variant  
["zat_b7_stalker_victim_1"] = "heroic, resilient, emotionally intense",              -- Spartacus  

--[[ OUTSKIRTS ]]--
["pri_monolith_monolith_trader_stalker"] = "a trader and is ritualistic, emotionally void and doctrinal",        -- Krolik  
["lider_monolith_haron"] = "the leader of the Monolith faction and is commanding, fanatical and spiritually fractured",                    -- Charon  
["pri_monolith_monolith_mechanic_stalker"] = "a technician and is methodical, silent and ideologically rigid",       -- Cleric  
["monolith_eidolon"] = "a young woman and who is the most feared and capable soldier of the Monolith faction. She is cryptic, detached and metaphysically obsessed",                          -- Eidolon  
["guid_pri_a15_mlr"] = "working as a guide taking people safely through the Zone for a fee and is friendly, curious and emotionally warm",                                 -- Tourist  
["trader_pri_a15_mlr"] = "a trader and is cheerful, erratic and emotionally unstable",                           -- Cashier  
["pri_medic_stalker"] = "a medic and is calm, nurturing and emotionally grounded",                              -- Yar  
["merc_pri_a18_mech_mlr"] = "a technician and is quiet, hardened and emotionally guarded",                           -- Trunk  
["pri_special_trader_mlr"] = "a trader and is guarded, pragmatic and emotionally distant",                       -- Meeker  
["merc_pri_grifon_mlr"] = "strategic, commanding, emotionally cold",                          -- Griffin  
["mechanic_monolith_kbo"] = "a technician and is precise, obedient and emotionally absent",                          -- Bracer  
["trader_monolith_kbo"] = "a trader and is silent, transactional and emotionally void",                          -- Olivar  
["stalker_stitch"] = "a medic and is loyal, steady and emotionally grounded",                                   -- Stitch  
["stalker_stitch_ms"] = "a medic and is loyal, steady and emotionally grounded",                                -- Stitch variant  
["stalker_stitch_oa"] = "a medic and is loyal, steady and emotionally grounded",                                -- Stitch variant  
["lost_stalker_strelok"] = "the living legend Strelok himself. He is the most famous, capable and dangerous man in the Zone and is enigmatic, quiet and emotionally fractured",                         -- Strelok  
["stalker_strelok_hb"] = "the living legend Strelok himself. He is the most famous, capable and dangerous man in the Zone and is enigmatic, quiet and emotionally fractured",                           -- Strelok variant  
["stalker_strelok_oa"] = "the living legend Strelok himself. He is the most famous, capable and dangerous man in the Zone and is enigmatic, quiet and emotionally fractured",                           -- Strelok variant  
["lazarus_stalker"] = "resilient, haunted, emotionally numb",                                 -- Lazarus  

}

return unique_characters
