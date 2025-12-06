local unique_characters =  {

    --[[ CORDON ]]--
	["actor"] = "",  -- Player stays blank  
	["esc_m_trader"] = "gruff, impatient and skeptical.",             -- Sidorovich  
	["m_trader"] = "gruff, impatient and skeptical.",                 -- Sidorovich  
	["esc_2_12_stalker_nimble"] = "cautious, observant and loyal",   -- Nimble  
	["esc_2_12_stalker_wolf"] = "confident, experienced, tactical, protective and reluctantly helpful", -- Wolf  
	["esc_2_12_stalker_fanat"] = "well-meaning and mentor-like but determined and zealous",       -- Fanatic  
	["esc_2_12_stalker_trader"] = "gruff, impatient and skeptical",  -- Sidorovich  
	["esc_smart_terrain_5_7_loner_mechanic_stalker"] = "is practical, quiet and reliable", -- Xenotech  
    ["devushka"] = "a young woman and who is loyal but defiant and jaded, is witty and uses dry humor and is subtly flirty",  -- Hip
	["esc_main_base_trader_mlr"] = "laid-back, sleepy and deadpan", -- Loris  
	["esc_3_16_military_trader"] = "stern, formal and efficient",    -- Major Zhurov  
	["army_south_mechan_mlr"] = "crude, irreverent and loyal",       -- Seryoga  

    --[[ GREAT SWAMPS ]]--
	["mar_smart_terrain_doc_doctor"] = "wise, calm and observant",               -- Doctor  
	["mar_smart_terrain_base_stalker_leader_marsh"] = "Cheerful, good-natured and loves vulgar jokes", -- Cold  
	["mar_base_stalker_tech"] = "analytical, quiet and methodical",             -- Novikov  
	["mar_base_owl_stalker_trader"] = "mysterious, aloof and perceptive",       -- Spore  
	["mar_smart_terrain_base_doctor"] = "observant, patient and intelligent",   -- Professor Kalancha  
	["guid_marsh_mlr"] = "easygoing, humorous and practical",                   -- Ivan Trodnik  
	["mar_base_stalker_barmen"] = "welcoming, grounded and supportive",         -- Librarian  

    --[[ DARKSCAPE ]]--
	["dasc_tech_mlr"] = "methodical, quiet and reliable",                       -- Polymer  
	["dasc_trade_mlr"] = "shrewd, persuasive and guarded",                      -- Cutter  
	["ds_domik_isg_leader"] = "intelligent, commanding, strategic and protective",           -- Major Hernandez  

    --[[ GARBAGE ]]--
["stalker_oleksandr_chernenko"] = "disillusioned, casual and impatient", 				--  Captain Oleksandr Chernenko
["hunter_gar_trader"] = "gruff, practical and blunt",                           -- Butcher  

    --[[ AGROPROM ]]--
["agr_smart_terrain_1_6_near_2_military_colonel_kovalski"] = "authoritative, but cynical, jaded and unscrupulous",         -- Major Kuznetsov  
["agr_1_6_medic_army_mlr"] = "compassionate and calm but still suffering from lingering after-effects of PTSD",                               -- Rogovets  
["agr_smart_terrain_1_6_army_trader_stalker"] = "wary, transactional and reserved",             -- Sergeant Spooner  
["agr_1_6_barman_army_mlr"] = "experienced, casual and relaxed.",                             -- Commander  
["agr_smart_terrain_1_6_army_mechanic_stalker"] = "precise, quiet and disciplined",             -- Lieutenant Kirilov

    --[[ AGROPROM UNDERGROUND ]]--
    ["agr_u_bandit_boss"] = "ruthless, manipulative and volatile",                      -- Reefer

    --[[ DARK VALLEY ]]--
["zat_b7_bandit_boss_sultan"] = "intelligent, manipulative, arrogant and calculating",       -- Sultan  
["val_smart_terrain_7_3_bandit_mechanic_stalker"] = "sarcastic and crude but loyal", -- Limpid  
["guid_dv_mal_mlr"] = "brash, impulsive and cocky",                             -- Pug  
["val_smart_terrain_7_4_bandit_trader_stalker"] = "sly, persuasive and guarded", -- Olivius  

    --[[ ROSTOK ]]--
	["bar_visitors_barman_stalker_trader"] = "pragmatic and gruff but friendly and loyal",         -- Barkeep  
	["bar_visitors_zhorik_stalker_guard2"] = "loud, aggressive and impatient",                   -- Zhorik  
	["bar_visitors_garik_stalker_guard"] = "guarded, quiet and focused",                         -- Garik  
	["bar_informator_mlr"] = "sneaky, opportunistic and evasive",                                -- Snitch  
	["guid_bar_stalker_navigator"] = "helpful, calm and observant",                              -- Navigator  
	["bar_arena_manager"] = "assertive, boisterous and competitive",                             -- Arnie  
	["bar_arena_guard"] = "stoic, loyal and silent",                                             -- Liolik  
	["bar_dolg_leader"] = "stern, strategic and loyal",                                          -- General Voronin  
	["bar_dolg_general_petrenko_stalker"] = "honorable, disciplined, unflappable and mission-focused",           -- Colonel Petrenko  
	["bar_dolg_medic"] = "calm, focused and melancholic",                                          -- Aspirin  
	["bar_visitors_stalker_mechanic"] = "gruff, alcoholic and emotionally worn",                 -- Mangun  
	["bar_zastava_2_commander"] = "tough, casual and no-nonsense",                           -- Sergeant Kitsenko  
	["bar_duty_security_squad_leader"] = "rigid, formal and protective",                         -- Captain Gavrilenko  

    --[[ TRUCK CEMETERY ]]--
    ["stalker_duty_girl"] = "a young woman and is loyal, determined and plain-spoken",                      -- Anna from Duty Expansion

    --[[ YANTAR ]]--
	["yan_stalker_sakharov"] = "polite, inquisitive, humble and no-nonsense",         -- Professor Sakharov  
	["mechanic_army_yan_mlr"] = "quiet, methodical and reliable",                      -- Peregrine  
	["yan_povar_army_mlr"] = "alcoholic, unreliable and emotionally numb",             -- Spirit  
	["yan_ecolog_kruglov"] = "anxious, cautious and dedicated",                        -- Professor Kruglov  

    --[[ ARMY WAREHOUSES ]]--
	["mil_smart_terrain_7_7_freedom_leader_stalker"] = "charismatic, strategic and protective",     -- Lukash  
	["mil_freedom_medic"] = "laid-back, humorous and emotionally grounded",                        -- Solid  
	["mil_smart_terrain_7_7_freedom_mechanic_stalker"] = "positive, optimistic, quiet and methodical",            -- Screw  
	["mil_smart_terrain_7_10_freedom_trader_stalker"] = "greedy, sarcastic and ruthless",          -- Skinflint  
	["mil_freedom_guid"] = "perceptive, hardened and cynical",                                     -- Leshiy  
	["stalker_gatekeeper"] = "steadfast, resolute and protective",                                   -- Gatekeeper  

    --[[ DEAD CITY ]]--
["cit_killers_merc_trader_stalker"] = "calculating, professional and emotionally detached",     -- Dushman  
["cit_killers_merc_mechanic_stalker"] = "gruff, focused and emotionally flat",                -- Hog  
["cit_killers_merc_barman_mlr"] = "sarcastic, secretive and emotionally numb",              -- Aslan  
["ds_killer_guide_main_base"] = "perceptive, quiet and tactical",                          -- Leopard  
["cit_killers_merc_medic_stalker"] = "clinical, efficient and emotionally distant",             -- Surgeon
  
    --[[ RED FOREST ]]--
	["red_forester_tech"] = "cryptic, reverent and emotionally unstable",         -- Forester  
	["red_greh_trader"] = "cold, taciturn and ideologically rigid",               -- Stribog  
	["red_greh_tech"] = "efficient, emotionally flat and doctrinal",              -- Dazhbog  

    --[[ DESERTED HOSPITAL ]]--
	["kat_greh_sabaoth"] = "ritualistic, emotionally void and doctrinal",         -- Chernobog (Katacombs variant)  
	["gen_greh_sabaoth"] = "fanatical, cryptic and spiritually fractured",        -- Chernobog (Generator variant)  
	["sar_greh_sabaoth"] = "obsessive, unstable and ideologically consumed",     -- Chernobog (Sarcophagus variant)  

    --[[ JUPITER ]]--
	["jup_b220_trapper"] = "gruff, weary and emotionally hardened",               -- Trapper  
	["jup_a6_stalker_barmen"] = "chill, humorous and emotionally resilient",          -- Hawaiian  
	["guid_jup_stalker_garik"] = "maintaining an act of being curious, upbeat and naive",                        -- Garry  
	["jup_a6_stalker_medik"] = "compassionate, calm and emotionally grounded",       -- Bonesetter  
	["zat_a2_stalker_mechanic"] = "sarcastic and emotionally unstable",   -- Cardan  
	["jup_b217_stalker_tech"] = "competent and friendly but scatterbrained",     -- Nitro  
	["jup_a6_freedom_trader_ashot"] = "loud, cheerful, humorous and chaotic",                  -- Ashot  
	["jup_a6_freedom_leader"] = "confident, strategic and charismatic",              -- Loki  
	["jup_b6_scientist_tech"] = "cold, disinterested and emotionally flat",            -- Tukarev  
	["jup_b6_scientist_nuclear_physicist"] = "anxious, cautious and intelligent", -- Professor Hermann  
	["jup_b6_scientist_biochemist"] = "pragmatic, quiet and friendly",    -- Professor Ozersky  
	["jup_depo_isg_leader"] = "commanding, strategic and protective",             -- Major Hernandez  
	["jup_depo_isg_tech"] = "meticulous, quiet and emotionally flat",                -- Lieutenant Maus  
	["jup_cont_mech_bandit"] = "sly, sarcastic and emotionally guarded",             -- Nile  
	["jup_cont_trader_bandit"] = "conniving, manipulative and emotionally cold",     -- Klenov  
	
    --[[ ZATON ]]--
["zat_stancia_mech_merc"] = "a young woman and who is excitable, bubbly and emotionally warm",                      -- Kolin  
["zat_stancia_trader_merc"] = "impatient, blunt and rude",              -- Vector  
["zat_a2_stalker_nimble"] = "resourceful, well-connected, fast-talking and lucky",                      -- Nimble  
["zat_b30_owl_stalker_trader"] = "secretive, transactional and emotionally distant",    -- Owl  
["zat_tech_mlr"] = "inventive, sarcastic and emotionally grounded",                     -- Spleen  
["zat_b22_stalker_medic"] = "gentle, calm and emotionally steady",                      -- Axel  
["zat_a2_stalker_barmen"] = "practical, welcoming and emotionally grounded",             -- Beard  
["zat_b18_noah"] = "paranoid, aggressive and mentally unstable",                        -- Noah  
["guid_zan_stalker_locman"] = "jovial, intuitive and emotionally perceptive",           -- Pilot  
["zat_b106_stalker_gonta"] = "grizzled, tactical and emotionally hardened",             -- Gonta  
["zat_b106_stalker_garmata"] = "stoic, loyal and emotionally steady",                   -- Garmata  
["zat_b106_stalker_crab"] = "alert, reactive and emotionally guarded",                  -- Crab  
["army_degtyarev_jup"] = "capable, disciplined, intelligent and emotionally resilient",          -- Colonel Degtyarev  
["army_degtyarev"] = "capable, disciplined, intelligent and emotionally resilient",              -- Degtyarev variant  
["stalker_rogue"] = "loyal, quiet and emotionally grounded",                            -- Rogue  
["stalker_rogue_ms"] = "loyal, quiet and emotionally grounded",                         -- Rogue variant  
["stalker_rogue_oa"] = "loyal, quiet and emotionally grounded",                         -- Rogue variant  
["zat_b7_stalker_victim_1"] = "heroic, resilient and emotionally intense",              -- Spartacus  

--[[ OUTSKIRTS ]]--
["stalker_western_goods_trader"] = "secretive, businesslike and guarded", 										-- Williams 'Ashes' Heades, Wester Goods trader
["pri_monolith_monolith_trader_stalker"] = "ritualistic, emotionally void and doctrinal",        -- Krolik  
["lider_monolith_haron"] = "commanding, fanatical and spiritually fractured",                    -- Charon  
["pri_monolith_monolith_mechanic_stalker"] = "methodical, silent and ideologically rigid",       -- Cleric  
["monolith_eidolon"] = "a young woman and who is cryptic, devoted and metaphysically obsessed",                          -- Eidolon  
["guid_pri_a15_mlr"] = "blunt, casual and flippant",                                 -- Tourist  
["trader_pri_a15_mlr"] = "cheerful, erratic and emotionally unstable",                           -- Cashier  
["pri_medic_stalker"] = "experienced, quiet and sharp",                              -- Yar  
["pri_a16_mech_mlr"] = "experienced, quiet and sharp",                              -- Yar  
["jup_b19_freedom_yar"] = "experienced, quiet and sharp",                              -- Yar  
["merc_pri_a18_mech_mlr"] = "pragmatic, hardened, and blunt",                           -- Trunk  
["pri_special_trader_mlr"] = "guarded, skittish, standoffish and careful",                       -- Meeker  
["merc_pri_grifon_mlr"] = "casual, confident and alert",                          -- Griffin  
["mechanic_monolith_kbo"] = "precise, obedient and emotionally absent",                          -- Bracer  
["trader_monolith_kbo"] = "silent, transactional and emotionally void",                          -- Olivar  
["stalker_stitch"] = "enthusiastic, cheerful and laid-back",                                   -- Stitch  
["stalker_stitch_ms"] = "enthusiastic, cheerful and laid-back",                                -- Stitch variant  
["stalker_stitch_oa"] = "enthusiastic, cheerful and laid-back",                                -- Stitch variant  
["lost_stalker_strelok"] = "enigmatic, quiet and emotionally fractured",                         -- Strelok  
["stalker_strelok_hb"] = "enigmatic, quiet and emotionally fractured",                           -- Strelok variant  
["stalker_strelok_oa"] = "enigmatic, quiet and emotionally fractured",                           -- Strelok variant  
["lazarus_stalker"] = "resilient, haunted and emotionally numb",                                 -- Lazarus  

}

return unique_characters
