import os
import requests


def get_style_prompt(style: str) -> str:
	base_prompt = (
		"Based on the provided floor plan image, create a realistic top-down 3D interior render of the same apartment. "
		"Completely erase and reconstruct any text, numbers, or symbols from the input — no visible letters, digits, or words must remain. "
		"Redraw those regions with appropriate wall/floor textures, not empty spaces. "
		"Keep the exact layout and proportions from the blueprint — do not alter the architecture. "
	)

	style_descriptions = {
		"minimalism": (
			"Minimalist interior design with clean lines, neutral color palette (whites, grays, beiges), "
			"minimal furniture, open spaces, natural light, simple geometric shapes, "
			"uncluttered surfaces, monochromatic scheme, high-quality materials like marble and wood."
		),
		"modern": (
			"Modern contemporary interior with sleek furniture, bold colors mixed with neutrals, "
			"metallic accents (chrome, gold), geometric patterns, statement lighting fixtures, "
			"glass and metal materials, vibrant artwork, mixed textures, urban sophistication."
		),
		"gothic": (
			"Gothic interior design with dark colors (deep purples, blacks, burgundy), "
			"ornate furniture with intricate details, dramatic lighting, velvet and brocade fabrics, "
			"arched windows, antique elements, rich textures, medieval-inspired decor, "
			"candles and chandeliers, luxurious and mysterious atmosphere."
		),
		"shabby_chic": (
			"Shabby chic interior with vintage furniture, distressed wood finishes, pastel colors "
			"(soft pinks, mint greens, lavender), floral patterns, whitewashed walls, "
			"rustic elements, antique accessories, lace and cotton fabrics, "
			"romantic and cozy atmosphere with worn elegance."
		),
		"japanese": (
			"Japanese interior design with tatami mats, sliding shoji screens, natural wood materials, "
			"neutral color palette (browns, beiges, whites), minimal furniture, low seating, "
			"zen garden elements, bamboo accents, paper lanterns, natural lighting, "
			"serene and peaceful atmosphere with emphasis on harmony and simplicity."
		),
		"scandinavian": (
			"Scandinavian interior design with light wood flooring, white and pastel walls, "
			"cozy textiles (wool, linen), natural materials, hygge elements, simple furniture, "
			"warm lighting, plants, neutral color palette with pops of color, "
			"functional and comfortable design with emphasis on coziness and natural light."
		),
	}

	style_text = style_descriptions.get(style, style_descriptions["scandinavian"])
	return f"{base_prompt}Interior style: {style_text}"


def _get_api_keys() -> list[str]:
	keys_env = os.getenv("STABILITY_API_KEYS", "").strip()
	if keys_env:
		separators = [",", ";", " "]
		for sep in separators:
			if sep in keys_env:
				parts = [p.strip() for p in keys_env.split(sep) if p.strip()]
				if parts:
					return parts
		return [keys_env]
	single = os.getenv("STABILITY_API_KEY")
	return [single] if single else []


def _get_style_reference_image_path(style: str, base_dir: str) -> str | None:
	static_dir = os.path.join(base_dir, "static", "images")
	mapping = {
		"minimalism": os.path.join(static_dir, "example_interior.png"),
		"modern": os.path.join(static_dir, "modern.png"),
		"gothic": os.path.join(static_dir, "gothic.png"),
		"shabby_chic": os.path.join(static_dir, "shabby-chic.png"),
		"japanese": os.path.join(static_dir, "japanese.png"),
		"scandinavian": os.path.join(static_dir, "scandinavian.png"),
	}
	path = mapping.get(style)
	return path if path and os.path.exists(path) else None


def generate_interior(prompt: str, image_path: str, output_path: str, style: str | None = None, base_dir: str | None = None) -> str | None:
	api_keys = _get_api_keys()
	if not api_keys:
		raise RuntimeError("STABILITY_API_KEY(S) is not set in environment")

	url = "https://api.stability.ai/v2beta/stable-image/control/structure"

	data = {
		"prompt": prompt,
		"output_format": "webp",
		"strength": 0.7,
	}
	
	# Получаем путь к reference image один раз
	ref_path = None
	if base_dir:
		ref_path = _get_style_reference_image_path(style or "", base_dir)
	
	last_status = None
	last_text = None
	
	# Пробуем каждый ключ, перечитывая файлы для каждой попытки
	for key in api_keys:
		headers = {"authorization": f"Bearer {key}", "accept": "image/*"}
		
		# Открываем файлы заново для каждой попытки
		with open(image_path, "rb") as f:
			files = {"image": f}
			
			# Открываем reference image, если есть
			ref_file = None
			if ref_path:
				ref_file = open(ref_path, "rb")
				files["reference_image"] = (os.path.basename(ref_path), ref_file, "image/png")
			
			try:
				response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
				last_status, last_text = response.status_code, getattr(response, "text", "")
				
				if response.status_code == 200:
					with open(output_path, "wb") as out:
						out.write(response.content)
					# Закрываем ref_file перед возвратом
					if ref_file:
						ref_file.close()
					return output_path
				
				# Если ошибка авторизации или лимита, пробуем следующий ключ
				if response.status_code in (401, 402, 403, 429):
					if ref_file:
						ref_file.close()
					continue
				
				# Для других ошибок прерываем цикл
				if ref_file:
					ref_file.close()
				break
				
			except requests.RequestException as e:
				last_text = str(e)
				if ref_file:
					ref_file.close()
				continue
	
	return None

