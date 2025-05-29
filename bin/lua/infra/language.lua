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

-- Optional helpers
function language.to_short(long_name)
  for _, v in pairs(language) do
    if v.long:lower() == long_name:lower() then
      return v.short
    end
  end
end

function language.to_long(short_code)
  local entry = language[short_code]
  return entry and entry.long or nil
end

return language
