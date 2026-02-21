-- domain/data/unique_npcs.lua
-- Set of technical section names for all unique/important NPCs.
-- Extracted from the `important_npcs` table in talker_game_queries.script.
-- Zero engine dependencies — pure data module.
local M = {}

local UNIQUE_NPC_IDS = {

    "actor",                                                    -- player


    --[[ CORDON ]]--
    "esc_m_trader",                                             -- Sidorovich
    "m_trader",                                                 -- Sidorovich
    "esc_2_12_stalker_nimble",                                  -- Nimble
    "esc_2_12_stalker_wolf",                                    -- Wolf
    "esc_2_12_stalker_fanat",                                   -- Fanatic
    "esc_2_12_stalker_trader",                                  -- Sidorovich
    "esc_smart_terrain_5_7_loner_mechanic_stalker",             -- Xenotech
    "devushka",                                                 -- Hip
    "esc_main_base_trader_mlr",                                 -- Loris
    "esc_3_16_military_trader",                                 -- Major Zhurov
    "army_south_mechan_mlr",                                    -- Seryoga

    --[[ GREAT SWAMPS ]]--
    "mar_smart_terrain_doc_doctor",                             -- Doctor
    "mar_smart_terrain_base_stalker_leader_marsh",              -- Cold
    "mar_base_stalker_tech",                                    -- Novikov
    "mar_base_owl_stalker_trader",                              -- Spore
    "mar_smart_terrain_base_doctor",                            -- Professor Kalancha
    "guid_marsh_mlr",                                           -- Ivan Trodnik
    "mar_base_stalker_barmen",                                  -- Librarian

    --[[ DARKSCAPE ]]--
    "dasc_tech_mlr",                                            -- Polymer
    "dasc_trade_mlr",                                           -- Cutter
    "ds_domik_isg_leader",                                      -- Major Hernandez

    --[[ GARBAGE ]]--
    "stalker_oleksandr_chernenko",                              -- Captain Oleksandr Chernenko
    "hunter_gar_trader",                                        -- Butcher

    --[[ AGROPROM ]]--
    "agr_smart_terrain_1_6_near_2_military_colonel_kovalski",   -- Major Kuznetsov
    "agr_1_6_medic_army_mlr",                                   -- Rogovets
    "agr_smart_terrain_1_6_army_trader_stalker",                -- Sergeant Spooner
    "agr_1_6_barman_army_mlr",                                  -- Commander
    "agr_smart_terrain_1_6_army_mechanic_stalker",              -- Lieutenant Kirilov

    --[[ AGROPROM UNDERGROUND ]]--
    "agr_u_bandit_boss",                                        -- Reefer

    --[[ DARK VALLEY ]]--
    "zat_b7_bandit_boss_sultan",                                -- Sultan
    "val_smart_terrain_7_3_bandit_mechanic_stalker",             -- Limpid
    "guid_dv_mal_mlr",                                          -- Pug
    "val_smart_terrain_7_4_bandit_trader_stalker",              -- Olivius

    --[[ ROSTOK ]]--
    "bar_visitors_barman_stalker_trader",                       -- Barkeep
    "bar_visitors_zhorik_stalker_guard2",                       -- Zhorik
    "bar_visitors_garik_stalker_guard",                         -- Garik
    "bar_informator_mlr",                                       -- Snitch
    "guid_bar_stalker_navigator",                               -- Navigator
    "bar_arena_manager",                                        -- Arnie
    "bar_arena_guard",                                          -- Liolik
    "bar_dolg_leader",                                          -- General Voronin
    "bar_dolg_general_petrenko_stalker",                        -- Colonel Petrenko
    "bar_dolg_medic",                                           -- Aspirin
    "bar_visitors_stalker_mechanic",                            -- Mangun
    "bar_zastava_2_commander",                                  -- Sergeant Kitsenko
    "bar_duty_security_squad_leader",                           -- Captain Gavrilenko

    --[[ TRUCK CEMETERY ]]--
    "stalker_duty_girl",                                        -- Anna from Duty Expansion

    --[[ YANTAR ]]--
    "yan_stalker_sakharov",                                     -- Professor Sakharov
    "mechanic_army_yan_mlr",                                    -- Peregrine
    "yan_povar_army_mlr",                                       -- Spirit
    "yan_ecolog_kruglov",                                       -- Professor Kruglov
    "yan_ecolog_semenov",                                       -- Professor Semenov

    --[[ ARMY WAREHOUSES ]]--
    "mil_smart_terrain_7_7_freedom_leader_stalker",             -- Lukash
    "mil_freedom_medic",                                        -- Solid
    "mil_smart_terrain_7_10_freedom_trader_stalker",            -- Skinflint
    "mil_smart_terrain_7_7_freedom_mechanic_stalker",           -- Screw
    "mil_freedom_guid",                                         -- Leshiy
    "stalker_gatekeeper",                                       -- Gatekeeper

    --[[ DEAD CITY ]]--
    "cit_killers_merc_mechanic_stalker",                        -- Hog
    "cit_killers_merc_trader_stalker",                          -- Dushman
    "ds_killer_guide_main_base",                                -- Leopard
    "cit_killers_merc_barman_mlr",                              -- Aslan
    "cit_killers_merc_medic_stalker",                           -- Surgeon

    --[[ RED FOREST ]]--
    "red_forester_tech",                                        -- Forester
    "red_greh_trader",                                          -- Stribog
    "red_greh_tech",                                            -- Dazhbog

    --[[ DESERTED HOSPITAL ]]--
    "kat_greh_sabaoth",                                         -- Chernobog and variants
    "gen_greh_sabaoth",
    "sar_greh_sabaoth",

    --[[ JUPITER ]]--
    "jup_b220_trapper",                                         -- Trapper
    "jup_a6_stalker_barmen",                                    -- Hawaiian
    "guid_jup_stalker_garik",                                   -- Garry
    "jup_a6_stalker_medik",                                     -- Bonesetter
    "zat_a2_stalker_mechanic",                                  -- Cardan
    "jup_b217_stalker_tech",                                    -- Nitro
    "jup_a6_freedom_trader_ashot",                              -- Ashot
    "jup_a6_freedom_leader",                                    -- Loki
    "jup_b6_scientist_tech",                                    -- Tukarev
    "jup_b6_scientist_nuclear_physicist",                       -- Professor Hermann
    "jup_b6_scientist_biochemist",                              -- Professor Ozersky
    "jup_depo_isg_leader",                                      -- Major Hernandez
    "jup_cont_mech_bandit",                                     -- Nile
    "jup_cont_trader_bandit",                                   -- Klenov
    "jup_depo_isg_tech",                                        -- Lieutenant Maus

    --[[ ZATON ]]--
    "zat_stancia_mech_merc",                                    -- Kolin
    "zat_stancia_trader_merc",                                  -- Vector
    "zat_a2_stalker_nimble",                                    -- Nimble
    "zat_b30_owl_stalker_trader",                               -- Owl
    "zat_tech_mlr",                                             -- Spleen
    "zat_b22_stalker_medic",                                    -- Axel
    "zat_a2_stalker_barmen",                                    -- Beard
    "zat_b18_noah",                                             -- Noah
    "guid_zan_stalker_locman",                                  -- Pilot
    "zat_b106_stalker_gonta",                                   -- Gonta
    "zat_b106_stalker_garmata",                                 -- Garmata
    "zat_b106_stalker_crab",                                    -- Crab
    "army_degtyarev_jup",                                       -- Colonel Degtyarev and variants
    "army_degtyarev",
    "stalker_rogue",                                            -- Rogue and variants
    "stalker_rogue_ms",
    "stalker_rogue_oa",
    "zat_b7_stalker_victim_1",                                  -- Spartacus

    --[[ OUTSKIRTS ]]--
    "stalker_western_goods_trader",                             -- Williams 'Ashes' Heades
    "pri_monolith_monolith_trader_stalker",                     -- Krolik
    "lider_monolith_haron",                                     -- Charon
    "pri_monolith_monolith_mechanic_stalker",                   -- Cleric
    "monolith_eidolon",                                         -- Eidolon
    "guid_pri_a15_mlr",                                         -- Tourist
    "trader_pri_a15_mlr",                                       -- Cashier
    "pri_medic_stalker",                                        -- Yar
    "pri_a16_mech_mlr",                                         -- Yar, variant
    "jup_b19_freedom_yar",                                      -- Yar, another variant
    "merc_pri_a18_mech_mlr",                                    -- Trunk
    "pri_special_trader_mlr",                                   -- Meeker
    "merc_pri_grifon_mlr",                                      -- Griffin
    "mechanic_monolith_kbo",                                    -- Bracer
    "trader_monolith_kbo",                                      -- Olivar
    "stalker_stitch",                                           -- Stitch and variants
    "stalker_stitch_ms",
    "stalker_stitch_oa",
    "lost_stalker_strelok",                                     -- Strelok and variants
    "stalker_strelok_hb",
    "stalker_strelok_oa",
    "lazarus_stalker",
}

-- Build a set for O(1) lookups
local _set = {}
for _, v in ipairs(UNIQUE_NPC_IDS) do
    _set[v] = true
end

--- Returns true if the given technical section name belongs to a unique NPC.
-- @param technical_name  Section / story-ID string (e.g. "esc_m_trader")
-- @return                boolean
function M.is_unique(technical_name)
    return _set[technical_name] == true
end

--- The set table for direct membership tests (value → true).
M.ids = _set

return M
