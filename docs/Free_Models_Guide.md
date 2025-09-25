# Free Models Guide

This guide provides a detailed walkthrough for setting up and using free AI models with TALKER. The best way to use free models is with the [LLM-API-Key-Proxy](https://github.com/Mirrowel/LLM-API-Key-Proxy), which helps you avoid rate limits and manage multiple API keys.

---

## Important Updates (September 2025)

*   **New Nvidia Models Added**: Several new models from Nvidia have been added to the guide, including `kimi-k2-instruct-0905` (recommended), `qwen3-next-80b-a3b-instruct` (recommended), `mistral-small-24b-instruct`, `deepseek-v3.1`, and various other versions of `qwen`.
*   **Model Reorganization**: The Nvidia model list has been reorganized into "Non-Thinking," "Thinking," and "Problematic" categories to help users better select models for their needs.
*   **Nvidia Performance Note**: A note has been added to the Nvidia section to inform users that model availability and performance can vary based on server load.

## Important Updates (July 2025)

*   **Chutes is No Longer Free**: Chutes has moved to a paid model(one-time, like openrouter). While this is a significant change, new free alternatives are being actively investigated and will be added to this guide as they become available.
*   **Community Impact**: The transition of Chutes to a paid service has unfortunately led to some users, particularly those generating NSFW content, migrating and abusing other free platforms. This has put a strain on those services, and their stability may be affected. Please use all services responsibly. Yes, blame Gooners. They killed Chutes for everyone and now they are killing the rest of the free services too(one already confirmed heavily impacted, with over 10x in usage).

---

### A Note on Thinking Models

"Thinking" models are designed for complex reasoning, which means they are often **considerably slower** than their non-thinking counterparts. For general use in the mod, **non-thinking models are usually the better choice** for a more responsive experience. However, **Gemini models are a notable exception**; their exceptional speed (Even Gemini Pro, which is faster and smarter than any other model on this list) makes them a powerful and viable option for thinking mode (In Auto MCM setting).

## Supported Free Providers
1.  **Gemini (Recommended)**: Gemini is known for its exceptional speed and solid intelligence, often outperforming other free services by a significant margin. This makes it an excellent choice for the "thinking mode" feature in TALKER, providing quick and coherent responses.
2.  **Nvidia**: Nvidia offers a robust selection of high-quality models. Their `kimi-k2-instruct` is a particularly strong performer for both reasoning and general dialogue. They also host free versions of popular models like DeepSeek and Qwen, though the specific rate limits for these are not always clear.

---

## 1. Gemini (Recommended)

Google's Gemini is the top choice for its generous free tier and strong performance. By creating multiple projects, you can generate several API keys (up to 12 per account in our experience), which dramatically increases your free usage limits when used with the API proxy. Do note that it is recommended to use multiple accounts instead of maxing out projects - I don't have concrete evidence, but multiple users had their projects "banned" for some reason, and they were unable to create new projects or API keys. So multiple accounts with 2-4 keys each is more than enough.

### Models and Rate Limits

Gemini and Gemma models offer a range of options, each with different trade-offs between speed, intelligence, and rate limits.

**Gemini Models**

| Model Name (Provider Prefix)                     | Speed      | Intelligence | Notes                                                                                                                                                               |
| ------------------------------------------------ | ---------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini/gemini-2.5-pro`                          | Slowest    | Smartest     | The most powerful model, ideal for complex dialogue and reasoning. Even as the "slowest" Gemini model, it's still faster than most non-Gemini models.                  |
| `gemini/gemini-2.5-flash`                        | Fast       | Smart        | **Recommended for most tasks.** A great balance of speed and intelligence, making it a versatile choice for both general use and thinking mode.                       |
| `gemini/gemini-2.5-flash-lite`     | Fastest    | Decent       | The quickest model, perfect for fast-paced interactions where raw speed is the top priority.                                                                        |

**Gemma Models**

| Model Name (Provider Prefix)       | Speed      | Intelligence | Notes                                                                                                                                                               |
| ---------------------------------- | ---------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini/gemma-3-27b-it`            | Fast       | Good         | A strong performer that cannot reason. With enough keys, its high rate limit allows for virtually unlimited use, making it a great fallback option for non-reasoning tasks. |

**Free Tier Rate Limits (Per key)**

| Model                                    | RPM | TPM     | RPD    |
| ---------------------------------------- | --- | ------- | ------ |
| Gemini 2.5 Pro                           | 5   | 125,000 | 50    |
| Gemini 2.5 Flash                         | 10  | 250,000 | 250    |
| Gemini 2.5 Flash-Lite Preview 06-17      | 15  | 250,000 | 1,000  |
| Gemma 3 & 3n                               | 30  | 15,000  | 14,400 |

*   **RPM**: Requests Per Minute
*   **TPM**: Tokens Per Minute
*   **RPD**: Requests Per Day

### How to Get Multiple Gemini API Keys

Follow these steps to get the maximum number of free keys from a single Google account:

**Step 1: Open the Google Cloud Console**
*   Navigate to the [Google Cloud Console](https://console.cloud.google.com/). If you aren't logged in, you'll be prompted to do so.

**Step 2: Open the Project Picker**
*   In the top-left corner of the dashboard, you'll see a project name (e.g., "My First Project"). Click on it to open the project selection window.

**Step 3: Create Multiple Projects**
*   In the project selection window, click the **"New Project"** button.
*   Give the project any name you like (e.g., "TALKER-Key-1"). The name isn't important as you won't see it again.
*   Repeat this process until Google Cloud no longer allows you to create new projects (usually around 12).

**Step 4: Generate an API Key for Each Project**
**WARNING**: It is strongly recommended **not** to use your main Google account for creating API keys. There have been reports of accounts being affected, though the exact reasons are unclear. To be safe, create a separate, dedicated Google account for generating API keys.

*   Now, go to the [Google AI Studio API Key Page](https://aistudio.google.com/app/apikey).
*   Click the **"Create API key"** button.
*   A dropdown menu will appear. Select one of the projects you just created.
*   An API key will be generated. **Copy this key immediately.**

**Step 5: Add Keys to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   Paste in the first Gemini API key you copied.
*   The script will ask if you want to add another key. Press `y` and then `Enter`.
*   Continue pasting in each new key you generate.

**Step 6: Repeat for All Projects**
*   Go back to the Google AI Studio page and repeat step 4 for all your projects, adding each new key to the proxy as you go. You can add all your keys in a single run of the `setup_env.bat` script.

**Step 7: Profit!**
*   You now have a pool of Gemini API keys. The proxy will automatically rotate through them, giving you a much higher free usage limit. You can even do this with multiple Google accounts for virtually unlimited use.

---


## 2. Nvidia

Nvidia offers a wide selection of high-quality models, making it a powerful option for experimentation. However, there are a few key limitations to keep in mind.

**Account and API Key Limitations**
*   You can only create one API key per Nvidia account.
*   Creating a new account requires phone number verification, which makes it difficult to acquire multiple keys.

**A Note on Rate Limits**
*   Nvidia's rate limits are not officially published. They appear to be generous and dependent on server load, but it's always best to use the service reasonably.

**A Note on Model Availability and Speed**
*   The availability and speed of Nvidia's models can vary significantly based on server load. A model that is unresponsive or very slow one day may be very fast the next. It's a good idea to have backup models in mind or test their speeds (in progress).

### How to Get an Nvidia API Key

**Step 1: Create and Verify Your Account**
*   Go to [build.nvidia.com](https://build.nvidia.com/) and create a new account or log in to an existing one.
*   You will need to verify your account with a phone number and email address to proceed.

**Step 2: Generate Your API Key**
*   Once you are logged in, navigate to the main dashboard.
*   Click the **"Get API Key"** button to generate your unique key.

**Step 3: Add the Key to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   When prompted, paste in your Nvidia API key.

### Available Models

Here are some of the notable models available through Nvidia's API:

**Non-Thinking Models**

| Model Name (Provider Prefix)                               | Notes                                                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `nvidia_nim/moonshotai/kimi-k2-instruct`                   | **Recommended.** One of the best models for storytelling and writing. Decently fast and reliable.     |
| `nvidia_nim/moonshotai/kimi-k2-instruct-0905`              | **Recommended.** A versioned variant of kimi-k2-instruct, as excellent for storytelling and writing, but usually slower or even unavailable.    |
| `nvidia_nim/qwen/qwen3-next-80b-a3b-instruct`              | **Recommended.** Non-thinking instruct version of Qwen, perfect for this use case - fast and almost always available.  |
| `nvidia_nim/meta/llama-4-maverick-17b-128e-instruct`       | A very fast model. Quality can vary and is very censored. But it is always available at high speed. It is sometimes too literal at what it does. Borders on unusable. |
| `nvidia_nim/google/gemma-3-27b-it`                         | A powerful, but small, model from Google that is a great alternative to other options. Faster then mistral.   |
| `nvidia_nim/mistralai/mistral-small-24b-instruct`          | Usually too slow, but can be used for instruct tasks when speed is not critical. A very good storytelling model. |


---
**Thinking Models** - Note that thinking models are often significantly slower than non-thinking models. For general use in the mod, non-thinking models are usually the better choice for a more responsive experience.

| Model Name (Provider Prefix)                               | Notes                                                                                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `nvidia_nim/deepseek-ai/deepseek-r1-0528`                  | The latest and most powerful version of DeepSeek-R1, excellent for reasoning tasks. Too slow with reasoning and commonly unavailable.                                     |
| `nvidia_nim/deepseek-ai/deepseek-r1`                       | The base version of DeepSeek-R1, a solid all-arounder. Faster, compared to 0528. Still not recommended   |
| `nvidia_nim/qwen/qwen3-next-80b-a3b-thinking`              | **Recommended.** A powerful and fast thinking model. Usually fast enough with reasoning—only recommended thinking model here.   |
| `nvidia_nim/bytedance/seed-oss-36b-instruct`               | Interesting small thinking model that is, sadly, not very fast.  |

---

***Problematic Models***

*At the time of writing, the following models were very problematic to run (unavailable or very slow) and may be unstable:*

| Model Name (Provider Prefix)                               | Notes                                                                                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `nvidia_nim/qwen/qwen3-235b-a22b`                          | A very large model from the Qwen family, capable of high-quality output but may be slower. (Thinking model by default in the mod)             |

---


## 3. Mistral (Preliminary)

Mistral.ai offers a free tier with seemingly very decent usage limits. This provider is currently being investigated for full integration with TALKER. In the meantime, you can add your Mistral API key yourself by following the proxy guide and experiment with it.

### How to Get a Mistral API Key

**Step 1: Create an Account**
*   Go to [mistral.ai](https://mistral.ai/) and create a new account or log in.

**Step 2: Generate Your API Key**
*   Navigate to the API section in your dashboard.
*   Click **"Create API Key"** and copy the generated key.

**Step 3: Add the Key to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   When prompted for providers, select Mistral and paste in your API key.
*   Note: The proxy may need configuration for Mistral if not already supported; check the repository for updates.

### Models and Notes
*   Models: To be added once fully investigated. Popular options include Mistral Small and Mistral Large, or Mixtral reasoning models, which show promise for both general and reasoning tasks.
*   Rate Limits: Free tier appears generous, but exact limits are under review.

For now, this allows early adopters to test Mistral's capabilities directly.
