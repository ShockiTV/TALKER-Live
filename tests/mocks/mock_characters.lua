-- Create characters
local Character = require('bin/lua/domain/model/character')

local anonsky = Character.new("1", "Anonsky", "experienced", "stalker", "shotgun")
local sarik = Character.new("2", "Sarik", "very inexperienced", "Freedom", "pistol")
local danila = Character.new("3", "Danila Matador", "inexperienced", "stalker", "rifle")
local fanatic = Character.new("4", "Fanatic", "experienced", "stalker", "Ak-47")
local egorka = Character.new("5", "Egorka Orderly", "very inexperienced", "stalker", "colt 1991")
local hip = Character.new("6", "Hip", "experienced", "stalker", "knife")

return {anonsky, sarik, danila, fanatic, egorka, hip}
