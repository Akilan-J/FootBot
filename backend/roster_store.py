import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.utils import logger
from backend.rag_engine import rag_engine

CACHE_PATH = settings.RAW_DATA_PATH.parent / "roster_cache.json"

# Predefined real-world squads (moved from frontend to simplify and centralize)
PREDEFINED_ROSTERS = {
    "manchester city": [
        {"name": "Ederson", "jersey": "31", "rating": 6.2, "pos": "GK", "photo": "frontend/assets/ederson.png", "age": "32", "val": "€35M", "height": "188 cm"},
        {"name": "K. Walker", "jersey": "2", "rating": 6.8, "pos": "RB", "photo": "", "age": "35", "val": "€15M", "height": "183 cm"},
        {"name": "R. Dias", "jersey": "3", "rating": 7.2, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "28", "val": "€80M", "height": "187 cm"},
        {"name": "M. Akanji", "jersey": "25", "rating": 7.0, "pos": "LCB", "photo": "", "age": "30", "val": "€45M", "height": "187 cm"},
        {"name": "J. Gvardiol", "jersey": "24", "rating": 7.5, "pos": "LB", "photo": "", "age": "24", "val": "€75M", "height": "185 cm"},
        {"name": "Rodri", "jersey": "16", "rating": 8.0, "pos": "LDM", "photo": "frontend/assets/rodri.png", "age": "29", "val": "€120M", "height": "190 cm"},
        {"name": "J. Stones", "jersey": "5", "rating": 6.8, "pos": "RDM", "photo": "", "age": "31", "val": "€38M", "height": "188 cm"},
        {"name": "B. Silva", "jersey": "20", "rating": 8.2, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm"},
        {"name": "K. De Bruyne", "jersey": "17", "rating": 8.5, "pos": "CAM", "photo": "frontend/assets/debruyne.png", "age": "34", "val": "€60M", "height": "181 cm"},
        {"name": "P. Foden", "jersey": "47", "rating": 8.7, "pos": "LAM", "photo": "frontend/assets/foden.png", "age": "25", "val": "€150M", "height": "179 cm"},
        {"name": "E. Haaland", "jersey": "9", "rating": 8.4, "pos": "ST", "photo": "frontend/assets/haaland.png", "age": "25", "val": "€180M", "height": "194 cm"},
    ],
    "real madrid": [
        {"name": "A. Lunin", "jersey": "13", "rating": 6.5, "pos": "GK", "photo": "", "age": "27", "val": "€25M", "height": "191 cm"},
        {"name": "D. Carvajal", "jersey": "2", "rating": 7.0, "pos": "RB", "photo": "", "age": "34", "val": "€12M", "height": "173 cm"},
        {"name": "A. Rüdiger", "jersey": "22", "rating": 7.8, "pos": "RCB", "photo": "", "age": "33", "val": "€25M", "height": "190 cm"},
        {"name": "Nacho", "jersey": "6", "rating": 6.4, "pos": "LCB", "photo": "", "age": "36", "val": "€4M", "height": "180 cm"},
        {"name": "F. Mendy", "jersey": "23", "rating": 6.6, "pos": "LB", "photo": "", "age": "30", "val": "€20M", "height": "180 cm"},
        {"name": "F. Valverde", "jersey": "15", "rating": 7.4, "pos": "RCM", "photo": "", "age": "27", "val": "€100M", "height": "182 cm"},
        {"name": "T. Kroos", "jersey": "8", "rating": 8.1, "pos": "CM", "photo": "", "age": "36", "val": "€10M", "height": "183 cm"},
        {"name": "E. Camavinga", "jersey": "12", "rating": 7.2, "pos": "LCM", "photo": "", "age": "23", "val": "€90M", "height": "182 cm"},
        {"name": "J. Bellingham", "jersey": "5", "rating": 8.3, "pos": "AM", "photo": "frontend/assets/bellingham.jpg", "age": "22", "val": "€180M", "height": "186 cm"},
        {"name": "Vinícius Jr.", "jersey": "7", "rating": 8.6, "pos": "LST", "photo": "", "age": "25", "val": "€150M", "height": "176 cm"},
        {"name": "Rodrygo", "jersey": "11", "rating": 7.9, "pos": "RST", "photo": "", "age": "25", "val": "€100M", "height": "174 cm"},
    ],
    "bayern": [
        {"name": "M. Neuer", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "40", "val": "€5M", "height": "193 cm"},
        {"name": "J. Kimmich", "jersey": "6", "rating": 8.6, "pos": "RB", "photo": "", "age": "31", "val": "€50M", "height": "177 cm"},
        {"name": "M. de Ligt", "jersey": "4", "rating": 7.0, "pos": "RCB", "photo": "", "age": "26", "val": "€65M", "height": "188 cm"},
        {"name": "E. Dier", "jersey": "15", "rating": 6.4, "pos": "LCB", "photo": "", "age": "32", "val": "€12M", "height": "188 cm"},
        {"name": "N. Mazraoui", "jersey": "40", "rating": 6.8, "pos": "LB", "photo": "", "age": "28", "val": "€30M", "height": "183 cm"},
        {"name": "K. Laimer", "jersey": "27", "rating": 6.1, "pos": "LDM", "photo": "", "age": "29", "val": "€30M", "height": "180 cm"},
        {"name": "A. Pavlović", "jersey": "45", "rating": 8.1, "pos": "RDM", "photo": "", "age": "22", "val": "€25M", "height": "188 cm"},
        {"name": "L. Sané", "jersey": "10", "rating": 7.8, "pos": "RAM", "photo": "", "age": "30", "val": "€70M", "height": "183 cm"},
        {"name": "T. Müller", "jersey": "25", "rating": 7.2, "pos": "CAM", "photo": "", "age": "36", "val": "€8M", "height": "185 cm"},
        {"name": "J. Musiala", "jersey": "42", "rating": 8.5, "pos": "LAM", "photo": "", "age": "23", "val": "€110M", "height": "184 cm"},
        {"name": "H. Kane", "jersey": "9", "rating": 8.0, "pos": "ST", "photo": "", "age": "32", "val": "€110M", "height": "188 cm"},
    ],
    "arsenal": [
        {"name": "D. Raya", "jersey": "22", "rating": 6.8, "pos": "GK", "photo": "", "age": "30", "val": "€35M", "height": "183 cm"},
        {"name": "B. White", "jersey": "4", "rating": 7.2, "pos": "RB", "photo": "", "age": "28", "val": "€55M", "height": "186 cm"},
        {"name": "W. Saliba", "jersey": "2", "rating": 7.7, "pos": "RCB", "photo": "", "age": "25", "val": "€80M", "height": "192 cm"},
        {"name": "G. Magalhães", "jersey": "6", "rating": 7.3, "pos": "LCB", "photo": "", "age": "28", "val": "€65M", "height": "190 cm"},
        {"name": "J. Kiwior", "jersey": "15", "rating": 6.4, "pos": "LB", "photo": "", "age": "26", "val": "€25M", "height": "189 cm"},
        {"name": "D. Rice", "jersey": "41", "rating": 8.0, "pos": "LCM", "photo": "", "age": "27", "val": "€110M", "height": "185 cm"},
        {"name": "Jorginho", "jersey": "20", "rating": 7.1, "pos": "RCM", "photo": "", "age": "34", "val": "€15M", "height": "180 cm"},
        {"name": "M. Ødegaard", "jersey": "8", "rating": 8.4, "pos": "AM", "photo": "", "age": "27", "val": "€95M", "height": "178 cm"},
        {"name": "B. Saka", "jersey": "7", "rating": 8.2, "pos": "RW", "photo": "", "age": "24", "val": "€130M", "height": "178 cm"},
        {"name": "G. Martinelli", "jersey": "11", "rating": 7.5, "pos": "LW", "photo": "", "age": "24", "val": "€80M", "height": "178 cm"},
        {"name": "K. Havertz", "jersey": "29", "rating": 7.9, "pos": "ST", "photo": "", "age": "26", "val": "€60M", "height": "193 cm"},
    ],
    "haiti": [
        {"name": "Duverger", "jersey": "1", "rating": 6.8, "pos": "GK", "photo": "", "age": "26", "val": "€500K", "height": "188 cm"},
        {"name": "Gérard", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "24", "val": "€300K", "height": "178 cm"},
        {"name": "Arise", "jersey": "4", "rating": 7.5, "pos": "RCB", "photo": "", "age": "25", "val": "€450K", "height": "185 cm"},
        {"name": "Adé", "jersey": "6", "rating": 7.1, "pos": "LCB", "photo": "", "age": "31", "val": "€200K", "height": "190 cm"},
        {"name": "Lacroix", "jersey": "3", "rating": 8.3, "pos": "LB", "photo": "", "age": "32", "val": "€400K", "height": "179 cm"},
        {"name": "Alceus", "jersey": "8", "rating": 7.0, "pos": "LCM", "photo": "", "age": "29", "val": "€350K", "height": "177 cm"},
        {"name": "L. Joseph", "jersey": "14", "rating": 8.1, "pos": "RCM", "photo": "", "age": "25", "val": "€1M", "height": "185 cm"},
        {"name": "R. Providence", "jersey": "10", "rating": 8.4, "pos": "AM", "photo": "", "age": "24", "val": "€2M", "height": "179 cm"},
        {"name": "Antoine", "jersey": "7", "rating": 6.9, "pos": "RW", "photo": "", "age": "32", "val": "€600K", "height": "178 cm"},
        {"name": "F. Pierrot", "jersey": "9", "rating": 8.6, "pos": "ST", "photo": "", "age": "31", "val": "€4M", "height": "194 cm"},
        {"name": "Nazon", "jersey": "11", "rating": 7.4, "pos": "LW", "photo": "", "age": "31", "val": "€1.5M", "height": "181 cm"},
    ],
    "new zealand": [
        {"name": "Paulsen", "jersey": "12", "rating": 5.8, "pos": "GK", "photo": "", "age": "23", "val": "€1M", "height": "195 cm"},
        {"name": "Payne", "jersey": "2", "rating": 5.4, "pos": "RB", "photo": "", "age": "32", "val": "€500K", "height": "188 cm"},
        {"name": "Boxall", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "37", "val": "€200K", "height": "188 cm"},
        {"name": "Bindon", "jersey": "6", "rating": 6.2, "pos": "LCB", "photo": "", "age": "21", "val": "€600K", "height": "186 cm"},
        {"name": "Cacace", "jersey": "3", "rating": 6.7, "pos": "LB", "photo": "", "age": "3M", "height": "183 cm"},
        {"name": "Bell", "jersey": "8", "rating": 6.1, "pos": "LDM", "photo": "", "age": "26", "val": "€1.2M", "height": "182 cm"},
        {"name": "Howieson", "jersey": "10", "rating": 5.9, "pos": "RDM", "photo": "", "age": "31", "val": "€400K", "height": "180 cm"},
        {"name": "Ruffer", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "25", "val": "€350K", "height": "178 cm"},
        {"name": "Just", "jersey": "14", "rating": 6.5, "pos": "CAM", "photo": "", "age": "25", "val": "€500K", "height": "177 cm"},
        {"name": "Garbett", "jersey": "11", "rating": 6.3, "pos": "LAM", "photo": "", "age": "24", "val": "€1.5M", "height": "188 cm"},
        {"name": "Wood", "jersey": "9", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€6M", "height": "191 cm"},
    ],
    "spain": [
        {"name": "U. Simón", "jersey": "23", "rating": 6.9, "pos": "GK", "photo": "", "age": "28", "val": "€30M", "height": "190 cm"},
        {"name": "M. Llorente", "jersey": "5", "rating": 6.6, "pos": "RB", "photo": "", "age": "31", "val": "€30M", "height": "184 cm"},
        {"name": "P. Cubarsí", "jersey": "22", "rating": 7.5, "pos": "RCB", "photo": "", "age": "19", "val": "€40M", "height": "184 cm"},
        {"name": "A. Laporte", "jersey": "14", "rating": 7.0, "pos": "LCB", "photo": "", "age": "32", "val": "€20M", "height": "191 cm"},
        {"name": "M. Cucurella", "jersey": "24", "rating": 6.2, "pos": "LB", "photo": "", "age": "27", "val": "€25M", "height": "173 cm"},
        {"name": "Pedri", "jersey": "20", "rating": 7.7, "pos": "RDM", "photo": "", "age": "23", "val": "€80M", "height": "174 cm"},
        {"name": "Rodri", "jersey": "16", "rating": 7.7, "pos": "LDM", "photo": "", "age": "29", "val": "€120M", "height": "190 cm"},
        {"name": "A. Baena", "jersey": "15", "rating": 6.5, "pos": "RAM", "photo": "", "age": "24", "val": "€40M", "height": "177 cm"},
        {"name": "F. Ruiz", "jersey": "8", "rating": 6.7, "pos": "CAM", "photo": "", "age": "30", "val": "€30M", "height": "189 cm"},
        {"name": "F. Torres", "jersey": "7", "rating": 6.9, "pos": "LAM", "photo": "", "age": "26", "val": "€35M", "height": "184 cm"},
        {"name": "M. Oyarzabal", "jersey": "21", "rating": 6.7, "pos": "ST", "photo": "", "age": "29", "val": "€40M", "height": "181 cm"},
    ],
    "peru": [
        {"name": "P. Gallese", "jersey": "1", "rating": 5.4, "pos": "GK", "photo": "", "age": "36", "val": "€1.5M", "height": "189 cm"},
        {"name": "J. Vidales", "jersey": "27", "rating": 6.5, "pos": "RB", "photo": "", "age": "33", "val": "€300K", "height": "175 cm"},
        {"name": "R. Garces", "jersey": "15", "rating": 6.4, "pos": "RCB", "photo": "", "age": "29", "val": "€700K", "height": "183 cm"},
        {"name": "F. Gruber", "jersey": "3", "rating": 6.1, "pos": "LCB", "photo": "", "age": "23", "val": "€400K", "height": "188 cm"},
        {"name": "O. Sonne", "jersey": "22", "rating": 5.9, "pos": "LB", "photo": "", "age": "25", "val": "€1.2M", "height": "187 cm"},
        {"name": "J. Pretell", "jersey": "6", "rating": 6.3, "pos": "RDM", "photo": "", "age": "26", "val": "€600K", "height": "170 cm"},
        {"name": "E. Noriega", "jersey": "8", "rating": 6.4, "pos": "LDM", "photo": "", "age": "24", "val": "€500K", "height": "178 cm"},
        {"name": "J. Vélez", "jersey": "11", "rating": 8.1, "pos": "RAM", "photo": "", "age": "29", "val": "€1M", "height": "176 cm"},
        {"name": "Y. Yotún", "jersey": "19", "rating": 6.6, "pos": "CAM", "photo": "", "age": "36", "val": "€1.5M", "height": "171 cm"},
        {"name": "M. López", "jersey": "4", "rating": 6.6, "pos": "LAM", "photo": "", "age": "26", "val": "€2M", "height": "176 cm"},
        {"name": "A. Ugarriza", "jersey": "9", "rating": 6.3, "pos": "ST", "photo": "", "age": "29", "val": "€500K", "height": "181 cm"},
    ],
    "liverpool": [
        {"name": "Alisson B.", "jersey": "1", "rating": 7.5, "pos": "GK", "photo": "", "age": "33", "val": "€28M", "height": "193 cm"},
        {"name": "Alexander-Arnold", "jersey": "66", "rating": 7.8, "pos": "RB", "photo": "", "age": "27", "val": "€70M", "height": "180 cm"},
        {"name": "I. Konaté", "jersey": "5", "rating": 7.1, "pos": "RCB", "photo": "", "age": "27", "val": "€45M", "height": "194 cm"},
        {"name": "V. van Dijk", "jersey": "4", "rating": 8.2, "pos": "LCB", "photo": "", "age": "34", "val": "€30M", "height": "193 cm"},
        {"name": "A. Robertson", "jersey": "26", "rating": 7.2, "pos": "LB", "photo": "", "age": "32", "val": "€30M", "height": "178 cm"},
        {"name": "W. Endo", "jersey": "3", "rating": 6.9, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm"},
        {"name": "Mac Allister", "jersey": "10", "rating": 7.6, "pos": "LDM", "photo": "", "age": "27", "val": "€75M", "height": "176 cm"},
        {"name": "Mohamed Salah", "jersey": "11", "rating": 8.4, "pos": "RAM", "photo": "", "age": "33", "val": "€55M", "height": "175 cm"},
        {"name": "Szoboszlai", "jersey": "8", "rating": 7.3, "pos": "CAM", "photo": "", "age": "25", "val": "€75M", "height": "187 cm"},
        {"name": "L. Díaz", "jersey": "7", "rating": 7.7, "pos": "LAM", "photo": "", "age": "29", "val": "€75M", "height": "180 cm"},
        {"name": "D. Núñez", "jersey": "9", "rating": 7.4, "pos": "ST", "photo": "", "age": "26", "val": "€65M", "height": "187 cm"},
    ],
    "philippines": [
        {"name": "N. Etheridge", "jersey": "1", "rating": 6.7, "pos": "GK", "photo": "", "age": "36", "val": "€350K", "height": "188 cm"},
        {"name": "C. de Murga", "jersey": "2", "rating": 6.2, "pos": "RB", "photo": "", "age": "39", "val": "€50K", "height": "180 cm"},
        {"name": "A. Aguinaldo", "jersey": "12", "rating": 6.4, "pos": "RCB", "photo": "", "age": "30", "val": "€150K", "height": "180 cm"},
        {"name": "C. Rontini", "jersey": "4", "rating": 6.3, "pos": "LCB", "photo": "", "age": "25", "val": "€150K", "height": "186 cm"},
        {"name": "D. Sato", "jersey": "11", "rating": 6.5, "pos": "LB", "photo": "", "age": "31", "val": "€200K", "height": "170 cm"},
        {"name": "Manny Ott", "jersey": "8", "rating": 6.6, "pos": "RDM", "photo": "", "age": "34", "val": "€200K", "height": "172 cm"},
        {"name": "K. Ingreso", "jersey": "14", "rating": 6.3, "pos": "LDM", "photo": "", "age": "31", "val": "€150K", "height": "178 cm"},
        {"name": "OJ Porteria", "jersey": "7", "rating": 6.8, "pos": "RAM", "photo": "", "age": "32", "val": "€200K", "height": "167 cm"},
        {"name": "Mike Ott", "jersey": "10", "rating": 6.9, "pos": "CAM", "photo": "", "age": "31", "val": "€225K", "height": "168 cm"},
        {"name": "S. Schröck", "jersey": "17", "rating": 7.0, "pos": "LAM", "photo": "", "age": "39", "val": "€50K", "height": "170 cm"},
        {"name": "P. Reichelt", "jersey": "9", "rating": 6.8, "pos": "ST", "photo": "", "age": "37", "val": "€100K", "height": "180 cm"},
    ],
    "guam": [
        {"name": "D. Jaye", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "32", "val": "€50K", "height": "187 cm"},
        {"name": "Alex Lee", "jersey": "2", "rating": 5.8, "pos": "RB", "photo": "", "age": "36", "val": "€25K", "height": "178 cm"},
        {"name": "T. Nicklaw", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "34", "val": "€50K", "height": "181 cm"},
        {"name": "M. Grimes", "jersey": "5", "rating": 5.9, "pos": "LCB", "photo": "", "age": "33", "val": "€25K", "height": "185 cm"},
        {"name": "J. Grindeland", "jersey": "3", "rating": 5.7, "pos": "LB", "photo": "", "age": "28", "val": "€10K", "height": "175 cm"},
        {"name": "M. Chargualaf", "jersey": "8", "rating": 6.0, "pos": "RDM", "photo": "", "age": "36", "val": "€10K", "height": "170 cm"},
        {"name": "I. Mariano", "jersey": "10", "rating": 6.1, "pos": "LDM", "photo": "", "age": "38", "val": "€10K", "height": "172 cm"},
        {"name": "M. Lopez", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "34", "val": "€50K", "height": "175 cm"},
        {"name": "J. Cunliffe", "jersey": "11", "rating": 6.5, "pos": "CAM", "photo": "", "age": "42", "val": "€10K", "height": "170 cm"},
        {"name": "S. Spindel", "jersey": "9", "rating": 5.9, "pos": "LAM", "photo": "", "age": "35", "val": "€10K", "height": "174 cm"},
        {"name": "S. Malcolm", "jersey": "19", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€50K", "height": "182 cm"},
    ],
    "japan": [
        {"name": "Z. Suzuki", "jersey": "1", "rating": 7.0, "pos": "GK", "photo": "", "age": "23", "val": "€15M", "height": "190 cm"},
        {"name": "Y. Sugawara", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "25", "val": "€12M", "height": "179 cm"},
        {"name": "K. Itakura", "jersey": "4", "rating": 7.3, "pos": "RCB", "photo": "", "age": "29", "val": "€15M", "height": "186 cm"},
        {"name": "K. Machida", "jersey": "15", "rating": 7.1, "pos": "LCB", "photo": "", "age": "28", "val": "€10M", "height": "190 cm"},
        {"name": "H. Ito", "jersey": "21", "rating": 7.4, "pos": "LB", "photo": "", "age": "27", "val": "€30M", "height": "188 cm"},
        {"name": "W. Endo", "jersey": "6", "rating": 7.6, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm"},
        {"name": "H. Morita", "jersey": "5", "rating": 7.5, "pos": "LDM", "photo": "", "age": "31", "val": "€15M", "height": "177 cm"},
        {"name": "R. Doan", "jersey": "8", "rating": 7.5, "pos": "RAM", "photo": "", "age": "27", "val": "€18M", "height": "172 cm"},
        {"name": "T. Minamino", "jersey": "10", "rating": 7.7, "pos": "CAM", "photo": "", "age": "31", "val": "€20M", "height": "174 cm"},
        {"name": "K. Mitoma", "jersey": "7", "rating": 8.2, "pos": "LAM", "photo": "", "age": "29", "val": "€45M", "height": "178 cm"},
        {"name": "A. Ueda", "jersey": "9", "rating": 7.3, "pos": "ST", "photo": "", "age": "27", "val": "€8M", "height": "182 cm"},
    ],
    "portugal": [
        {"name": "Diogo Costa", "jersey": "22", "rating": 7.4, "pos": "GK", "photo": "", "age": "26", "val": "€45M", "height": "186 cm"},
        {"name": "João Cancelo", "jersey": "20", "rating": 7.5, "pos": "RB", "photo": "", "age": "32", "val": "€25M", "height": "182 cm"},
        {"name": "Rúben Dias", "jersey": "4", "rating": 7.8, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "29", "val": "€80M", "height": "187 cm"},
        {"name": "Pepe", "jersey": "3", "rating": 7.2, "pos": "LCB", "photo": "", "age": "43", "val": "€1M", "height": "188 cm"},
        {"name": "Nuno Mendes", "jersey": "19", "rating": 7.6, "pos": "LB", "photo": "", "age": "23", "val": "€55M", "height": "176 cm"},
        {"name": "João Palhinha", "jersey": "6", "rating": 7.5, "pos": "RDM", "photo": "", "age": "30", "val": "€50M", "height": "190 cm"},
        {"name": "Vitinha", "jersey": "23", "rating": 7.9, "pos": "LDM", "photo": "", "age": "26", "val": "€55M", "height": "172 cm"},
        {"name": "Bernardo Silva", "jersey": "10", "rating": 8.0, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm"},
        {"name": "Bruno Fernandes", "jersey": "8", "rating": 8.3, "pos": "CAM", "photo": "", "age": "31", "val": "€70M", "height": "179 cm"},
        {"name": "Rafael Leão", "jersey": "17", "rating": 8.1, "pos": "LAM", "photo": "", "age": "26", "val": "€75M", "height": "188 cm"},
        {"name": "C. Ronaldo", "jersey": "7", "rating": 8.2, "pos": "ST", "photo": "", "age": "41", "val": "€15M", "height": "187 cm"},
    ]
}

def normalize_name(name: str) -> str:
    """Normalizes team names to lower case, stripping spaces and extra qualifiers like U20."""
    n = name.lower().strip()
    n = re.sub(r"\s+u\d+\b", "", n)
    n = re.sub(r"\s+u-\d+\b", "", n)
    return n

def load_cache() -> Dict[str, List[Dict[str, Any]]]:
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading roster cache from {CACHE_PATH}: {e}")
    return {}

def save_cache(cache: Dict[str, List[Dict[str, Any]]]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving roster cache to {CACHE_PATH}: {e}")

def get_real_world_roster(team_name: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns the real-world starting XI squad for a team.
    Checks predefined list first, then local cache, and finally queries LLM if key is available.
    """
    norm_name = normalize_name(team_name)
    logger.info(f"Resolving real-world roster for: '{team_name}' (normalized: '{norm_name}')")

    # 1. Predefined list
    for k, v in PREDEFINED_ROSTERS.items():
        if k == norm_name or k in norm_name or norm_name in k:
            logger.info(f"Roster for '{team_name}' found in PREDEFINED_ROSTERS under '{k}'")
            return v

    # 2. Local cache lookup
    cache = load_cache()
    if norm_name in cache:
        logger.info(f"Roster for '{team_name}' found in local cache.")
        return cache[norm_name]

    # 3. LLM Query if OpenAI is initialized
    if rag_engine.openai_client is not None:
        logger.info(f"Roster for '{team_name}' not found in cache. Querying LLM...")
        try:
            prompt = f"""You are a professional football database helper. Your job is to return the actual, real-world current (or recent) starting XI lineup/squad for the football team '{team_name}'.
You must output exactly 11 players in JSON format.
Each player must have exactly the following keys:
- 'name': The real player's full name (e.g. 'Bukayo Saka' or 'A. Lunin')
- 'jersey': Their squad/jersey number as a string (e.g. '7')
- 'rating': A realistic SofaScore performance rating as a float between 6.0 and 9.5 (e.g. 7.4)
- 'pos': One of the standard tactical positions: 'GK', 'RB', 'RCB', 'LCB', 'LB', 'LDM', 'RDM', 'LCM', 'CM', 'RCM', 'LAM', 'CAM', 'RAM', 'LW', 'ST', 'RW', 'LST', 'RST', 'LM', 'RM', 'AM'. There must be exactly one 'GK' (goalkeeper).
- 'photo': Always an empty string ""
- 'age': The player's age as a string (e.g. '24')
- 'val': The player's market value as a string (e.g. '€120M' or '€5M')
- 'height': The player's height as a string (e.g. '178 cm')

Return ONLY a raw valid JSON array. Do not write any markdown code wrappers (like ```json), notes, explanations, or extra characters. Simply return the raw JSON text."""
            
            completion = rag_engine.openai_client.chat.completions.create(
                model=rag_engine.model_name,
                messages=[
                    {"role": "system", "content": "You are a database system returning raw JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            response_text = completion.choices[0].message.content.strip()
            
            # Clean markdown wrappers if any
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            roster = json.loads(response_text)
            if isinstance(roster, list) and len(roster) == 11:
                # Validate structures
                valid = True
                required_keys = {"name", "jersey", "rating", "pos", "photo", "age", "val", "height"}
                for p in roster:
                    if not required_keys.issubset(p.keys()):
                        valid = False
                        break
                
                if valid:
                    logger.info(f"Successfully retrieved and validated LLM roster for '{team_name}'. Caching...")
                    cache[norm_name] = roster
                    save_cache(cache)
                    return roster
                else:
                    logger.warning("LLM returned JSON list but it was missing required player keys.")
            else:
                logger.warning(f"LLM did not return exactly 11 players. Length: {len(roster) if isinstance(roster, list) else 'not a list'}")
        except Exception as e:
            logger.error(f"Failed to query LLM for roster: {e}")
    else:
        logger.warning("OpenAI client not initialized. Cannot fetch roster via LLM.")

    return None
