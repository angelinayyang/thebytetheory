# -*- coding: utf-8 -*-
"""Enriches recipes.json with a per-serving calorie estimate and more specific
ingredients. It reads the existing recipes.json (which holds the descriptions,
methods, and tips) and patches in the calorie + ingredient fields, so re-running
it is safe. recipes.json remains the live data file — edit it directly to change
descriptions or steps, then run `python init_db.py`.
"""
import json
from pathlib import Path
import re

HERE = Path(__file__).parent
recipes = json.loads((HERE / "recipes.json").read_text())

# Per-serving calorie estimates (rounded; clearly approximate).
CAL = {
 "Microwave Mug Pancake":380,"Toaster Waffle Upgrade":320,"Perfect Fried Egg":95,
 "Cheesy Omelette":330,"Loaded Bagel":350,"Crispy Oven Bacon":180,
 "Dorm Ramen, Upgraded":480,"Grilled Cheese":410,"Microwave Mac & Cheese":520,
 "Loaded Nachos":450,"Egg Salad Sandwich":430,"Garlic Bread":230,"Oven Fries":250,
 "Weeknight Chickpea Curry":480,"Spaghetti Aglio e Olio":520,"Smashburger":600,
 "Sheet-Pan Roast Chicken":540,"Pan-Seared Salmon":370,"Weeknight Meatballs":480,
 "Homemade Pizza":600,"Steak Night":560,"Beef Tacos":450,"Pan-Fried Pork Dumplings":380,
 "Burrito Bowl":560,"Loaded Hot Dog":360,"California Roll Sushi":350,
 "Chewy Chocolate Chip Cookies":160,"Mug Brownie":450,"No-Bake Cheesecake Cup":390,
 "Cinnamon Apple Pie":330,"Classic Glazed Donuts":250,"Lemon Tart":340,
 "Vanilla Pudding":220,"Strawberry Shortcake":380,"Portuguese-Style Egg Tarts":180,
 "Stovetop Popcorn":150,"Loaded Cheese Puffs":200,"Microwave Potato Chips":180,
 "Kettle Oatmeal Jar":350,"PB Banana Smoothie":330,
}

# More specific ingredient lists (the kind of detail a good recipe gives).
ING = {
"Microwave Mug Pancake":["4 tbsp (30 g) all-purpose flour","1 tbsp granulated sugar","1/2 tsp baking powder","Pinch of salt","3 tbsp whole milk","1 tbsp unsalted butter, melted","1 large egg","Pure maple syrup or berry jam, to serve"],
"Toaster Waffle Upgrade":["2 frozen Belgian-style waffles","1/3 cup full-fat Greek yogurt (or whipped cream)","1/2 cup fresh mixed berries (strawberries, blueberries)","1 tbsp runny honey or maple syrup","1 tbsp chopped toasted almonds or granola (optional)"],
"Perfect Fried Egg":["1 large egg","1 tsp unsalted butter or olive oil","Flaky sea salt","Freshly ground black pepper"],
"Cheesy Omelette":["2 large eggs","1 tbsp whole milk","1/4 cup grated sharp cheddar (or gruyère)","1 tsp unsalted butter","Salt","Black pepper","Optional: chopped chives or a pinch of chili flakes"],
"Loaded Bagel":["1 plain or sesame bagel, halved","2–3 tbsp full-fat cream cheese","1/2 ripe tomato, sliced","A few thin slices of red onion","1/2 tsp everything bagel seasoning","Salt and pepper"],
"Crispy Oven Bacon":["6–8 strips streaky (American-style) bacon","Freshly ground black pepper (optional)"],
"Dorm Ramen, Upgraded":["1 pack instant ramen (chicken or shoyu), with seasoning","1 large egg","1 green onion, sliced","1 tsp light soy sauce","1/2 tsp toasted sesame oil","Optional: handful of frozen sweetcorn or baby spinach","Optional: chili crisp, to finish"],
"Grilled Cheese":["2 thick slices sourdough or white sandwich bread","2 slices sharp cheddar or American (or a handful, grated)","1–2 tbsp salted butter, softened","Optional: sliced tomato or a smear of Dijon"],
"Microwave Mac & Cheese":["1/2 cup elbow macaroni","1/2 cup water","1/4 cup whole milk","1/2 cup grated sharp cheddar","Salt","Optional: pinch of mustard powder or paprika"],
"Loaded Nachos":["Big handful of salted tortilla chips","1 cup grated Monterey Jack or medium cheddar","1/4 cup pickled jalapeños","1/4 cup chunky salsa","2 tbsp sour cream","Optional: canned black beans, drained; sliced green onion"],
"Egg Salad Sandwich":["3 large eggs","2 tbsp full-fat mayonnaise","1 tsp Dijon mustard","1 green onion, finely sliced (optional)","Salt and pepper","4 slices soft white or wholemeal bread","Crisp romaine lettuce, to serve"],
"Garlic Bread":["1/2 day-old baguette (or ciabatta)","3 tbsp salted butter, softened","2 cloves fresh garlic, finely grated","1 tbsp chopped flat-leaf parsley","Pinch of salt","Optional: grated parmesan"],
"Oven Fries":["2 medium russet potatoes (high-starch — they crisp best)","1 tbsp neutral oil","1/2 tsp salt","1/2 tsp smoked paprika","Black pepper"],
"Weeknight Chickpea Curry":["1 tbsp neutral oil","1 yellow onion, diced","2 cloves garlic, minced","2 tbsp Thai red or yellow curry paste (or 1 tbsp curry powder)","1 can (400 g) chickpeas, drained","1 can (400 ml) full-fat coconut milk","1 handful baby spinach (optional)","Salt","Cooked basmati rice, to serve"],
"Spaghetti Aglio e Olio":["200 g dried spaghetti","1/3 cup extra-virgin olive oil","4 cloves garlic, thinly sliced","1/2 tsp red chili flakes","Handful of flat-leaf parsley, chopped","Salt","Optional: grated parmesan (omit to keep vegan)"],
"Smashburger":["150 g 80/20 ground beef (chuck)","1 soft potato burger bun","1 slice American cheese","Salt and pepper","A little neutral oil","Toppings: dill pickles, sliced onion, burger sauce"],
"Sheet-Pan Roast Chicken":["4 bone-in, skin-on chicken thighs","2 Yukon Gold or a handful of baby potatoes, chunked","1 yellow onion, cut into wedges","2 tbsp olive oil","1 tsp smoked paprika","1 tsp salt","Black pepper","Optional: lemon wedges, fresh rosemary"],
"Pan-Seared Salmon":["1 skin-on salmon fillet","1 tsp neutral oil","Flaky salt","Black pepper","Lemon wedge, to serve"],
"Weeknight Meatballs":["300 g 80/20 ground beef","1 large egg","1/4 cup panko breadcrumbs","1 clove garlic, minced","2 tbsp grated parmesan (optional)","Salt and pepper","1 jar (about 400 g) marinara sauce","Dried spaghetti, to serve"],
"Homemade Pizza":["1 pizza base or naan","1/3 cup pizza sauce or passata","1 cup grated low-moisture mozzarella","Toppings of choice (peppers, mushrooms, olives)","1 tsp olive oil","Pinch of dried oregano"],
"Steak Night":["1 ribeye or sirloin steak (about 200 g)","1 tsp neutral oil","Flaky salt","Black pepper","1 tbsp unsalted butter","1 clove garlic, crushed"],
"Beef Tacos":["250 g 80/20 ground beef","1 tbsp taco seasoning (or cumin, paprika, garlic powder)","4–6 small corn tortillas","1 cup shredded romaine lettuce","1/2 cup grated cheddar","Salsa, sour cream, lime, to serve"],
"Pan-Fried Pork Dumplings":["12 frozen pork dumplings (gyoza)","1 tbsp neutral oil","1/3 cup water","For the dip: 2 tbsp light soy sauce, 1 tsp rice vinegar, a few drops sesame oil, chili to taste"],
"Burrito Bowl":["1 cup cooked long-grain or jasmine rice","1 can black beans, drained and rinsed","1/2 cup sweetcorn","1/2 cup chunky salsa","1/2 ripe avocado, sliced","Handful of shredded romaine","Optional: grated cheddar, sour cream, lime, hot sauce"],
"Loaded Hot Dog":["1 beef hot dog (frankfurter)","1 soft hot dog bun","Yellow mustard and ketchup","2 tbsp diced white onion","1 tbsp sweet relish or sliced dill pickles","Optional: grated cheddar, crispy fried onions"],
"California Roll Sushi":["1 cup short-grain sushi rice","1.25 cups water","2 tbsp rice vinegar","1 tbsp sugar","1/2 tsp salt","2 sheets nori","4 imitation crab sticks","1/2 cucumber, cut into strips","1/2 ripe avocado, sliced","Toasted sesame seeds, soy sauce, to serve"],
"Chewy Chocolate Chip Cookies":["115 g (1/2 cup) unsalted butter, softened","1/2 cup light brown sugar","1/4 cup granulated sugar","1 large egg","1 tsp vanilla extract","1.5 cups all-purpose flour","1/2 tsp baking soda","1/4 tsp salt","1 cup semisweet chocolate chips"],
"Mug Brownie":["4 tbsp all-purpose flour","4 tbsp granulated sugar","2 tbsp unsweetened cocoa powder","Pinch of salt","3 tbsp whole milk","2 tbsp neutral oil","Optional: a few semisweet chocolate chips"],
"No-Bake Cheesecake Cup":["1/2 cup full-fat cream cheese, softened","1/4 cup heavy (double) cream","3 tbsp granulated sugar","1/2 tsp vanilla extract","1/2 cup crushed graham crackers or digestive biscuits","1 tbsp unsalted butter, melted","1/2 cup fresh berries"],
"Cinnamon Apple Pie":["2 sheets shortcrust or pie pastry","3 Granny Smith apples, peeled and thinly sliced","1/3 cup granulated sugar","1 tsp ground cinnamon","1 tbsp all-purpose flour","1 tbsp unsalted butter","1 egg, beaten (for glaze)"],
"Classic Glazed Donuts":["2.5 cups all-purpose (or bread) flour","1 packet (7 g) instant yeast","3/4 cup warm whole milk","1/4 cup sugar","1 large egg","3 tbsp unsalted butter, softened","1/2 tsp salt","Neutral oil, for frying","For glaze: 1 cup powdered sugar + 2 tbsp milk"],
"Lemon Tart":["1 pre-baked sweet tart shell","3 large eggs","2 lemons (juice and zest)","3/4 cup granulated sugar","1/3 cup unsalted butter","Optional: powdered sugar, to finish"],
"Vanilla Pudding":["2 cups whole milk","1/4 cup granulated sugar","2 tbsp cornstarch","1 large egg yolk","1 tsp vanilla extract","Pinch of salt"],
"Strawberry Shortcake":["1 sponge or pound cake (bought, or a simple 4-egg sponge)","2 cups fresh strawberries, sliced","2 tbsp granulated sugar","1 cup heavy (double) cream","1 tbsp powdered sugar","1/2 tsp vanilla extract"],
"Portuguese-Style Egg Tarts":["1 sheet all-butter puff pastry, thawed","3 large egg yolks","1/2 cup whole milk","1/3 cup granulated sugar","1 tsp vanilla extract","1 tsp cornstarch"],
"Stovetop Popcorn":["1/3 cup popcorn kernels","2 tbsp neutral oil (high smoke point)","Salt","Optional: melted butter or nutritional yeast"],
"Loaded Cheese Puffs":["1 big handful of cheese puffs (curls)","Optional: a few dashes of hot sauce","Optional: squeeze of lime"],
"Microwave Potato Chips":["1 russet potato (starchy — crisps best)","1 tsp neutral oil","Salt","Optional: paprika or other seasoning"],
"Kettle Oatmeal Jar":["1/2 cup quick-cooking oats","3/4 cup boiling water","1/2 ripe banana, sliced","1 tbsp natural peanut butter","Pinch of salt","Optional: honey, cinnamon, or berries"],
"PB Banana Smoothie":["1 ripe banana (frozen, if possible)","1 tbsp natural peanut butter","1 cup milk (any kind)","2 tbsp rolled oats","A few ice cubes","Optional: 1 tsp honey, pinch of cinnamon"],
}

# How many people each recipe feeds at its written amounts (drives portion
# scaling for cooking groups).
BASE_SERVINGS = {
 "Microwave Mug Pancake":1,"Toaster Waffle Upgrade":1,"Perfect Fried Egg":1,
 "Cheesy Omelette":1,"Loaded Bagel":1,"Crispy Oven Bacon":3,
 "Dorm Ramen, Upgraded":1,"Grilled Cheese":1,"Microwave Mac & Cheese":1,
 "Loaded Nachos":2,"Egg Salad Sandwich":2,"Garlic Bread":3,"Oven Fries":2,
 "Weeknight Chickpea Curry":3,"Spaghetti Aglio e Olio":2,"Smashburger":1,
 "Sheet-Pan Roast Chicken":3,"Pan-Seared Salmon":1,"Weeknight Meatballs":3,
 "Homemade Pizza":2,"Steak Night":1,"Beef Tacos":3,"Pan-Fried Pork Dumplings":2,
 "Burrito Bowl":1,"Loaded Hot Dog":1,"California Roll Sushi":2,
 "Chewy Chocolate Chip Cookies":6,"Mug Brownie":1,"No-Bake Cheesecake Cup":2,
 "Cinnamon Apple Pie":6,"Classic Glazed Donuts":8,"Lemon Tart":6,
 "Vanilla Pudding":2,"Strawberry Shortcake":4,"Portuguese-Style Egg Tarts":6,
 "Stovetop Popcorn":2,"Loaded Cheese Puffs":1,"Microwave Potato Chips":1,
 "Kettle Oatmeal Jar":1,"PB Banana Smoothie":1,
}

for r in recipes:
    r["calories"] = CAL[r["name"]]
    r["ingredients"] = ING[r["name"]]
    m = re.match(r"\s*(\d+)", r["servings"])   # numeric base for scaling
    r["base_servings"] = int(m.group(1)) if m else 2
    r["base_servings"] = BASE_SERVINGS[r["name"]]

(HERE / "recipes.json").write_text(json.dumps(recipes, indent=2, ensure_ascii=False))
print(f"enriched {len(recipes)} recipes with calories + specific ingredients")
missing = [r["name"] for r in recipes if r["name"] not in CAL or r["name"] not in ING]
print("missing:", missing or "none")
