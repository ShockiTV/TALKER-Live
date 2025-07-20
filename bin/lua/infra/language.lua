-- language.lua
local language = {
  any = { short = "", long = "Any" },
  en = { short = "en", long = "English" },
  uk = { short = "uk", long = "Ukrainian" },
  ru = { short = "ru", long = "Russian" },
  fr = { short = "fr", long = "French" },
  de = { short = "de", long = "German" },
  es = { short = "es", long = "Spanish" },
  it = { short = "it", long = "Italian" },
  pl = { short = "pl", long = "Polish" },
  zh = { short = "zh", long = "Chinese" },
  ja = { short = "ja", long = "Japanese" }
}

function language.to_short(long_name)
  local name = long_name:lower()
  for _, v in pairs(language) do
    if type(v) == "table" and v.long:lower() == name then
      return v.short
    end
  end
  return nil
end

function language.to_long(short_code)
  local entry = language[short_code]
  return entry and entry.long or nil
end

return language