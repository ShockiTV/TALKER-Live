-- message_normalizer.lua
-- This module ensures that message sequences are compliant with strict APIs like Gemini.
-- It merges consecutive messages of the same role and ensures no trailing system messages.

local logger = require("framework.logger")

local normalizer = {}

--- Normalizes a list of chat messages for Gemini compatibility.
-- @param messages Table array of {role, content}
-- @return Normalized table array
function normalizer.normalize(messages)
	if not messages or #messages == 0 then
		return messages
	end

	local normalized = {}
	local current_msg = nil

	for i, msg in ipairs(messages) do
		local role = msg.role
		local content = msg.content or ""

		if not current_msg then
			-- First message
			current_msg = { role = role, content = content }
		elseif current_msg.role == role then
			-- Consecutive roles: merge content
			current_msg.content = current_msg.content .. "\n\n" .. content
		else
			-- Different role: push current and start new
			table.insert(normalized, current_msg)
			current_msg = { role = role, content = content }
		end
	end

	-- Push the last message
	if current_msg then
		table.insert(normalized, current_msg)
	end

	-- GEMINI COMPATIBILITY FIXES:

	-- 1. No Trailing System Message
	-- If the last message is 'system', merge it into the preceding message.
	if #normalized > 1 and normalized[#normalized].role == "system" then
		logger.debug("Normalizing: Merging trailing system message into preceding message.")
		local last_system = table.remove(normalized)
		local target = normalized[#normalized]
		target.content = target.content .. "\n\n" .. last_system.content
	end

	return normalized
end

return normalizer
