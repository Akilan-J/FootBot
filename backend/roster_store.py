import json
import re
import requests
import unicodedata
import urllib.parse
import fcntl
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.utils import logger
from backend.rag_engine import rag_engine

CACHE_PATH = settings.RAW_DATA_PATH.parent / "roster_cache.json"

# Predefined real-world squads (moved from frontend to simplify and centralize)
PREDEFINED_ROSTERS = {
    "manchester city": [
        {"name": "Ederson", "jersey": "31", "rating": 6.2, "pos": "GK", "photo": "frontend/assets/ederson.png", "age": "32", "val": "€35M", "height": "188 cm", "sofa_id": "84511"},
        {"name": "K. Walker", "jersey": "2", "rating": 6.8, "pos": "RB", "photo": "", "age": "35", "val": "€15M", "height": "183 cm", "sofa_id": "14298"},
        {"name": "R. Dias", "jersey": "3", "rating": 7.2, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "28", "val": "€80M", "height": "187 cm", "sofa_id": "830225"},
        {"name": "M. Akanji", "jersey": "25", "rating": 7.0, "pos": "LCB", "photo": "", "age": "30", "val": "€45M", "height": "187 cm", "sofa_id": "316654"},
        {"name": "J. Gvardiol", "jersey": "24", "rating": 7.5, "pos": "LB", "photo": "", "age": "24", "val": "€75M", "height": "185 cm", "sofa_id": "966601"},
        {"name": "Rodri", "jersey": "16", "rating": 8.0, "pos": "LDM", "photo": "frontend/assets/rodri.png", "age": "29", "val": "€120M", "height": "190 cm", "sofa_id": "333346"},
        {"name": "J. Stones", "jersey": "5", "rating": 6.8, "pos": "RDM", "photo": "", "age": "31", "val": "€38M", "height": "188 cm", "sofa_id": "148425"},
        {"name": "B. Silva", "jersey": "20", "rating": 8.2, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm", "sofa_id": "244465"},
        {"name": "K. De Bruyne", "jersey": "17", "rating": 8.5, "pos": "CAM", "photo": "frontend/assets/debruyne.png", "age": "34", "val": "€60M", "height": "181 cm", "sofa_id": "40387"},
        {"name": "P. Foden", "jersey": "47", "rating": 8.7, "pos": "LAM", "photo": "frontend/assets/foden.png", "age": "25", "val": "€150M", "height": "179 cm", "sofa_id": "860471"},
        {"name": "E. Haaland", "jersey": "9", "rating": 8.4, "pos": "ST", "photo": "frontend/assets/haaland.png", "age": "25", "val": "€180M", "height": "194 cm", "sofa_id": "826725"},
    ],
    "real madrid": [
        {"name": "A. Lunin", "jersey": "13", "rating": 6.5, "pos": "GK", "photo": "", "age": "27", "val": "€25M", "height": "191 cm", "sofa_id": "860431"},
        {"name": "D. Carvajal", "jersey": "2", "rating": 7.0, "pos": "RB", "photo": "", "age": "34", "val": "€12M", "height": "173 cm", "sofa_id": "136015"},
        {"name": "A. Rüdiger", "jersey": "22", "rating": 7.8, "pos": "RCB", "photo": "", "age": "33", "val": "€25M", "height": "190 cm", "sofa_id": "153164"},
        {"name": "Nacho", "jersey": "6", "rating": 6.4, "pos": "LCB", "photo": "", "age": "36", "val": "€4M", "height": "180 cm", "sofa_id": "136025"},
        {"name": "F. Mendy", "jersey": "23", "rating": 6.6, "pos": "LB", "photo": "", "age": "30", "val": "€20M", "height": "180 cm", "sofa_id": "792073"},
        {"name": "F. Valverde", "jersey": "15", "rating": 7.4, "pos": "RCM", "photo": "", "age": "27", "val": "€100M", "height": "182 cm", "sofa_id": "829285"},
        {"name": "T. Kroos", "jersey": "8", "rating": 8.1, "pos": "CM", "photo": "", "age": "36", "val": "€10M", "height": "183 cm", "sofa_id": "15570"},
        {"name": "E. Camavinga", "jersey": "12", "rating": 7.2, "pos": "LCM", "photo": "", "age": "23", "val": "€90M", "height": "182 cm", "sofa_id": "925345"},
        {"name": "J. Bellingham", "jersey": "5", "rating": 8.3, "pos": "AM", "photo": "frontend/assets/bellingham.jpg", "age": "22", "val": "€180M", "height": "186 cm", "sofa_id": "923363"},
        {"name": "Vinícius Jr.", "jersey": "7", "rating": 8.6, "pos": "LST", "photo": "", "age": "25", "val": "€150M", "height": "176 cm", "sofa_id": "862217"},
        {"name": "Rodrygo", "jersey": "11", "rating": 7.9, "pos": "RST", "photo": "", "age": "25", "val": "€100M", "height": "174 cm", "sofa_id": "923348"},
    ],
    "bayern": [
        {"name": "M. Neuer", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "40", "val": "€5M", "height": "193 cm", "sofa_id": "14846"},
        {"name": "J. Kimmich", "jersey": "6", "rating": 8.6, "pos": "RB", "photo": "", "age": "31", "val": "€50M", "height": "177 cm", "sofa_id": "256926"},
        {"name": "M. de Ligt", "jersey": "4", "rating": 7.0, "pos": "RCB", "photo": "", "age": "26", "val": "€65M", "height": "188 cm", "sofa_id": "825227"},
        {"name": "E. Dier", "jersey": "15", "rating": 6.4, "pos": "LCB", "photo": "", "age": "32", "val": "€12M", "height": "188 cm", "sofa_id": "149817"},
        {"name": "N. Mazraoui", "jersey": "40", "rating": 6.8, "pos": "LB", "photo": "", "age": "28", "val": "€30M", "height": "183 cm", "sofa_id": "863339"},
        {"name": "K. Laimer", "jersey": "27", "rating": 6.1, "pos": "LDM", "photo": "", "age": "29", "val": "€30M", "height": "180 cm", "sofa_id": "324151"},
        {"name": "A. Pavlović", "jersey": "45", "rating": 8.1, "pos": "RDM", "photo": "", "age": "22", "val": "€25M", "height": "188 cm", "sofa_id": "1138865"},
        {"name": "L. Sané", "jersey": "10", "rating": 7.8, "pos": "RAM", "photo": "", "age": "30", "val": "€70M", "height": "183 cm", "sofa_id": "234720"},
        {"name": "T. Müller", "jersey": "25", "rating": 7.2, "pos": "CAM", "photo": "", "age": "36", "val": "€8M", "height": "185 cm", "sofa_id": "14842"},
        {"name": "J. Musiala", "jersey": "42", "rating": 8.5, "pos": "LAM", "photo": "", "age": "23", "val": "€110M", "height": "184 cm", "sofa_id": "966373"},
        {"name": "H. Kane", "jersey": "9", "rating": 8.0, "pos": "ST", "photo": "", "age": "32", "val": "€110M", "height": "188 cm", "sofa_id": "124233"},
    ],
    "arsenal": [
        {"name": "D. Raya", "jersey": "22", "rating": 6.8, "pos": "GK", "photo": "", "age": "30", "val": "€35M", "height": "183 cm", "sofa_id": ""},
        {"name": "B. White", "jersey": "4", "rating": 7.2, "pos": "RB", "photo": "", "age": "28", "val": "€55M", "height": "186 cm", "sofa_id": ""},
        {"name": "W. Saliba", "jersey": "2", "rating": 7.7, "pos": "RCB", "photo": "", "age": "25", "val": "€80M", "height": "192 cm", "sofa_id": ""},
        {"name": "G. Magalhães", "jersey": "6", "rating": 7.3, "pos": "LCB", "photo": "", "age": "28", "val": "€65M", "height": "190 cm", "sofa_id": ""},
        {"name": "J. Kiwior", "jersey": "15", "rating": 6.4, "pos": "LB", "photo": "", "age": "26", "val": "€25M", "height": "189 cm", "sofa_id": ""},
        {"name": "D. Rice", "jersey": "41", "rating": 8.0, "pos": "LCM", "photo": "", "age": "27", "val": "€110M", "height": "185 cm", "sofa_id": ""},
        {"name": "Jorginho", "jersey": "20", "rating": 7.1, "pos": "RCM", "photo": "", "age": "34", "val": "€15M", "height": "180 cm", "sofa_id": ""},
        {"name": "M. Ødegaard", "jersey": "8", "rating": 8.4, "pos": "AM", "photo": "", "age": "27", "val": "€95M", "height": "178 cm", "sofa_id": ""},
        {"name": "B. Saka", "jersey": "7", "rating": 8.2, "pos": "RW", "photo": "", "age": "24", "val": "€130M", "height": "178 cm", "sofa_id": ""},
        {"name": "G. Martinelli", "jersey": "11", "rating": 7.5, "pos": "LW", "photo": "", "age": "24", "val": "€80M", "height": "178 cm", "sofa_id": ""},
        {"name": "K. Havertz", "jersey": "29", "rating": 7.9, "pos": "ST", "photo": "", "age": "26", "val": "€60M", "height": "193 cm", "sofa_id": ""},
    ],
    "haiti": [
        {"name": "Duverger", "jersey": "1", "rating": 6.8, "pos": "GK", "photo": "", "age": "26", "val": "€500K", "height": "188 cm", "sofa_id": ""},
        {"name": "Gérard", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "24", "val": "€300K", "height": "178 cm", "sofa_id": ""},
        {"name": "Arise", "jersey": "4", "rating": 7.5, "pos": "RCB", "photo": "", "age": "25", "val": "€450K", "height": "185 cm", "sofa_id": ""},
        {"name": "Adé", "jersey": "6", "rating": 7.1, "pos": "LCB", "photo": "", "age": "31", "val": "€200K", "height": "190 cm", "sofa_id": ""},
        {"name": "Lacroix", "jersey": "3", "rating": 8.3, "pos": "LB", "photo": "", "age": "32", "val": "€400K", "height": "179 cm", "sofa_id": ""},
        {"name": "Alceus", "jersey": "8", "rating": 7.0, "pos": "LCM", "photo": "", "age": "29", "val": "€350K", "height": "177 cm", "sofa_id": ""},
        {"name": "L. Joseph", "jersey": "14", "rating": 8.1, "pos": "RCM", "photo": "", "age": "25", "val": "€1M", "height": "185 cm", "sofa_id": ""},
        {"name": "R. Providence", "jersey": "10", "rating": 8.4, "pos": "AM", "photo": "", "age": "24", "val": "€2M", "height": "179 cm", "sofa_id": ""},
        {"name": "Antoine", "jersey": "7", "rating": 6.9, "pos": "RW", "photo": "", "age": "32", "val": "€600K", "height": "178 cm", "sofa_id": ""},
        {"name": "F. Pierrot", "jersey": "9", "rating": 8.6, "pos": "ST", "photo": "", "age": "31", "val": "€4M", "height": "194 cm", "sofa_id": "832791"},
        {"name": "Nazon", "jersey": "11", "rating": 7.4, "pos": "LW", "photo": "", "age": "31", "val": "€1.5M", "height": "181 cm", "sofa_id": ""},
    ],
    "new zealand": [
        {"name": "Paulsen", "jersey": "12", "rating": 5.8, "pos": "GK", "photo": "", "age": "23", "val": "€1M", "height": "195 cm", "sofa_id": ""},
        {"name": "Payne", "jersey": "2", "rating": 5.4, "pos": "RB", "photo": "", "age": "32", "val": "€500K", "height": "188 cm", "sofa_id": ""},
        {"name": "Boxall", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "37", "val": "€200K", "height": "188 cm", "sofa_id": ""},
        {"name": "Bindon", "jersey": "6", "rating": 6.2, "pos": "LCB", "photo": "", "age": "21", "val": "€600K", "height": "186 cm", "sofa_id": ""},
        {"name": "Cacace", "jersey": "3", "rating": 6.7, "pos": "LB", "photo": "", "age": "3M", "height": "183 cm", "sofa_id": ""},
        {"name": "Bell", "jersey": "8", "rating": 6.1, "pos": "LDM", "photo": "", "age": "26", "val": "€1.2M", "height": "182 cm", "sofa_id": ""},
        {"name": "Howieson", "jersey": "10", "rating": 5.9, "pos": "RDM", "photo": "", "age": "31", "val": "€400K", "height": "180 cm", "sofa_id": ""},
        {"name": "Ruffer", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "25", "val": "€350K", "height": "178 cm", "sofa_id": ""},
        {"name": "Just", "jersey": "14", "rating": 6.5, "pos": "CAM", "photo": "", "age": "25", "val": "€500K", "height": "177 cm", "sofa_id": ""},
        {"name": "Garbett", "jersey": "11", "rating": 6.3, "pos": "LAM", "photo": "", "age": "24", "val": "€1.5M", "height": "188 cm", "sofa_id": ""},
        {"name": "Wood", "jersey": "9", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€6M", "height": "191 cm", "sofa_id": "46654"},
    ],
    "spain": [
        {"name": "U. Simón", "jersey": "23", "rating": 6.9, "pos": "GK", "photo": "", "age": "28", "val": "€30M", "height": "190 cm", "sofa_id": "865554"},
        {"name": "M. Llorente", "jersey": "5", "rating": 6.6, "pos": "RB", "photo": "", "age": "31", "val": "€30M", "height": "184 cm", "sofa_id": "266580"},
        {"name": "P. Cubarsí", "jersey": "22", "rating": 7.5, "pos": "RCB", "photo": "", "age": "19", "val": "€40M", "height": "184 cm", "sofa_id": "1269389"},
        {"name": "A. Laporte", "jersey": "14", "rating": 7.0, "pos": "LCB", "photo": "", "age": "32", "val": "€20M", "height": "191 cm", "sofa_id": "148386"},
        {"name": "M. Cucurella", "jersey": "24", "rating": 6.2, "pos": "LB", "photo": "", "age": "27", "val": "€25M", "height": "173 cm", "sofa_id": "828552"},
        {"name": "Pedri", "jersey": "20", "rating": 7.7, "pos": "RDM", "photo": "", "age": "23", "val": "€80M", "height": "174 cm", "sofa_id": "959253"},
        {"name": "Rodri", "jersey": "16", "rating": 7.7, "pos": "LDM", "photo": "", "age": "29", "val": "€120M", "height": "190 cm", "sofa_id": "333346"},
        {"name": "A. Baena", "jersey": "15", "rating": 6.5, "pos": "RAM", "photo": "", "age": "24", "val": "€40M", "height": "177 cm", "sofa_id": "966601"},
        {"name": "F. Ruiz", "jersey": "8", "rating": 6.7, "pos": "CAM", "photo": "", "age": "30", "val": "€30M", "height": "189 cm", "sofa_id": "351656"},
        {"name": "F. Torres", "jersey": "7", "rating": 6.9, "pos": "LAM", "photo": "", "age": "26", "val": "€35M", "height": "184 cm", "sofa_id": "864696"},
        {"name": "M. Oyarzabal", "jersey": "21", "rating": 6.7, "pos": "ST", "photo": "", "age": "29", "val": "€40M", "height": "181 cm", "sofa_id": "385686"},
    ],
    "peru": [
        {"name": "P. Gallese", "jersey": "1", "rating": 5.4, "pos": "GK", "photo": "", "age": "36", "val": "€1.5M", "height": "189 cm", "sofa_id": ""},
        {"name": "J. Vidales", "jersey": "27", "rating": 6.5, "pos": "RB", "photo": "", "age": "33", "val": "€300K", "height": "175 cm", "sofa_id": ""},
        {"name": "R. Garces", "jersey": "15", "rating": 6.4, "pos": "RCB", "photo": "", "age": "29", "val": "€700K", "height": "183 cm", "sofa_id": ""},
        {"name": "F. Gruber", "jersey": "3", "rating": 6.1, "pos": "LCB", "photo": "", "age": "23", "val": "€400K", "height": "188 cm", "sofa_id": ""},
        {"name": "O. Sonne", "jersey": "22", "rating": 5.9, "pos": "LB", "photo": "", "age": "25", "val": "€1.2M", "height": "187 cm", "sofa_id": ""},
        {"name": "J. Pretell", "jersey": "6", "rating": 6.3, "pos": "RDM", "photo": "", "age": "26", "val": "€600K", "height": "170 cm", "sofa_id": ""},
        {"name": "E. Noriega", "jersey": "8", "rating": 6.4, "pos": "LDM", "photo": "", "age": "24", "val": "€500K", "height": "178 cm", "sofa_id": ""},
        {"name": "J. Vélez", "jersey": "11", "rating": 8.1, "pos": "RAM", "photo": "", "age": "29", "val": "€1M", "height": "176 cm", "sofa_id": ""},
        {"name": "Y. Yotún", "jersey": "19", "rating": 6.6, "pos": "CAM", "photo": "", "age": "36", "val": "€1.5M", "height": "171 cm", "sofa_id": ""},
        {"name": "M. López", "jersey": "4", "rating": 6.6, "pos": "LAM", "photo": "", "age": "26", "val": "€2M", "height": "176 cm", "sofa_id": ""},
        {"name": "A. Ugarriza", "jersey": "9", "rating": 6.3, "pos": "ST", "photo": "", "age": "29", "val": "€500K", "height": "181 cm", "sofa_id": ""},
    ],
    "liverpool": [
        {"name": "Alisson B.", "jersey": "1", "rating": 7.5, "pos": "GK", "photo": "", "age": "33", "val": "€28M", "height": "193 cm", "sofa_id": "333100"},
        {"name": "Alexander-Arnold", "jersey": "66", "rating": 7.8, "pos": "RB", "photo": "", "age": "27", "val": "€70M", "height": "180 cm", "sofa_id": "824147"},
        {"name": "I. Konaté", "jersey": "5", "rating": 7.1, "pos": "RCB", "photo": "", "age": "27", "val": "€45M", "height": "194 cm", "sofa_id": "865778"},
        {"name": "V. van Dijk", "jersey": "4", "rating": 8.2, "pos": "LCB", "photo": "", "age": "34", "val": "€30M", "height": "193 cm", "sofa_id": "138136"},
        {"name": "A. Robertson", "jersey": "26", "rating": 7.2, "pos": "LB", "photo": "", "age": "32", "val": "€30M", "height": "178 cm", "sofa_id": "235300"},
        {"name": "W. Endo", "jersey": "3", "rating": 6.9, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm", "sofa_id": "232470"},
        {"name": "Mac Allister", "jersey": "10", "rating": 7.6, "pos": "LDM", "photo": "", "age": "27", "val": "€75M", "height": "176 cm", "sofa_id": "868357"},
        {"name": "Mohamed Salah", "jersey": "11", "rating": 8.4, "pos": "RAM", "photo": "", "age": "33", "val": "€55M", "height": "175 cm", "sofa_id": "144181"},
        {"name": "Szoboszlai", "jersey": "8", "rating": 7.3, "pos": "CAM", "photo": "", "age": "25", "val": "€75M", "height": "886360", "sofa_id": "886360"},
        {"name": "L. Díaz", "jersey": "7", "rating": 7.7, "pos": "LAM", "photo": "", "age": "29", "val": "€75M", "height": "180 cm", "sofa_id": "862662"},
        {"name": "D. Núñez", "jersey": "9", "rating": 7.4, "pos": "ST", "photo": "", "age": "26", "val": "€65M", "height": "187 cm", "sofa_id": "884586"},
    ],
    "philippines": [
        {"name": "N. Etheridge", "jersey": "1", "rating": 6.7, "pos": "GK", "photo": "", "age": "36", "val": "€350K", "height": "188 cm", "sofa_id": ""},
        {"name": "C. de Murga", "jersey": "2", "rating": 6.2, "pos": "RB", "photo": "", "age": "39", "val": "€50K", "height": "180 cm", "sofa_id": ""},
        {"name": "A. Aguinaldo", "jersey": "12", "rating": 6.4, "pos": "RCB", "photo": "", "age": "30", "val": "€150K", "height": "180 cm", "sofa_id": ""},
        {"name": "C. Rontini", "jersey": "4", "rating": 6.3, "pos": "LCB", "photo": "", "age": "25", "val": "€150K", "height": "186 cm", "sofa_id": ""},
        {"name": "D. Sato", "jersey": "11", "rating": 6.5, "pos": "LB", "photo": "", "age": "31", "val": "€200K", "height": "170 cm", "sofa_id": ""},
        {"name": "Manny Ott", "jersey": "8", "rating": 6.6, "pos": "RDM", "photo": "", "age": "34", "val": "€200K", "height": "172 cm", "sofa_id": ""},
        {"name": "K. Ingreso", "jersey": "14", "rating": 6.3, "pos": "LDM", "photo": "", "age": "31", "val": "€150K", "height": "178 cm", "sofa_id": ""},
        {"name": "OJ Porteria", "jersey": "7", "rating": 6.8, "pos": "RAM", "photo": "", "age": "32", "val": "€200K", "height": "167 cm", "sofa_id": ""},
        {"name": "Mike Ott", "jersey": "10", "rating": 6.9, "pos": "CAM", "photo": "", "age": "31", "val": "€225K", "height": "168 cm", "sofa_id": ""},
        {"name": "S. Schröck", "jersey": "17", "rating": 7.0, "pos": "LAM", "photo": "", "age": "39", "val": "€50K", "height": "170 cm", "sofa_id": ""},
        {"name": "P. Reichelt", "jersey": "9", "rating": 6.8, "pos": "ST", "photo": "", "age": "37", "val": "€100K", "height": "180 cm", "sofa_id": ""},
    ],
    "guam": [
        {"name": "D. Jaye", "jersey": "1", "rating": 5.9, "pos": "GK", "photo": "", "age": "32", "val": "€50K", "height": "187 cm", "sofa_id": ""},
        {"name": "Alex Lee", "jersey": "2", "rating": 5.8, "pos": "RB", "photo": "", "age": "36", "val": "€25K", "height": "178 cm", "sofa_id": ""},
        {"name": "T. Nicklaw", "jersey": "4", "rating": 6.0, "pos": "RCB", "photo": "", "age": "34", "val": "€50K", "height": "181 cm", "sofa_id": ""},
        {"name": "M. Grimes", "jersey": "5", "rating": 5.9, "pos": "LCB", "photo": "", "age": "33", "val": "€25K", "height": "185 cm", "sofa_id": ""},
        {"name": "J. Grindeland", "jersey": "3", "rating": 5.7, "pos": "LB", "photo": "", "age": "28", "val": "€10K", "height": "175 cm", "sofa_id": ""},
        {"name": "M. Chargualaf", "jersey": "8", "rating": 6.0, "pos": "RDM", "photo": "", "age": "36", "val": "€10K", "height": "170 cm", "sofa_id": ""},
        {"name": "I. Mariano", "jersey": "10", "rating": 6.1, "pos": "LDM", "photo": "", "age": "38", "val": "€10K", "height": "172 cm", "sofa_id": ""},
        {"name": "M. Lopez", "jersey": "7", "rating": 6.2, "pos": "RAM", "photo": "", "age": "34", "val": "€50K", "height": "175 cm", "sofa_id": ""},
        {"name": "J. Cunliffe", "jersey": "11", "rating": 6.5, "pos": "CAM", "photo": "", "age": "42", "val": "€10K", "height": "170 cm", "sofa_id": ""},
        {"name": "S. Spindel", "jersey": "9", "rating": 5.9, "pos": "LAM", "photo": "", "age": "35", "val": "€10K", "height": "174 cm", "sofa_id": ""},
        {"name": "S. Malcolm", "jersey": "19", "rating": 6.1, "pos": "ST", "photo": "", "age": "34", "val": "€50K", "height": "182 cm", "sofa_id": ""},
    ],
    "japan": [
        {"name": "Z. Suzuki", "jersey": "1", "rating": 7.0, "pos": "GK", "photo": "", "age": "23", "val": "€15M", "height": "190 cm", "sofa_id": "986427"},
        {"name": "Y. Sugawara", "jersey": "2", "rating": 7.2, "pos": "RB", "photo": "", "age": "25", "val": "€12M", "height": "179 cm", "sofa_id": "943960"},
        {"name": "K. Itakura", "jersey": "4", "rating": 7.3, "pos": "RCB", "photo": "", "age": "29", "val": "€15M", "height": "186 cm", "sofa_id": "830214"},
        {"name": "K. Machida", "jersey": "15", "rating": 7.1, "pos": "LCB", "photo": "", "age": "28", "val": "€10M", "height": "190 cm", "sofa_id": "834273"},
        {"name": "H. Ito", "jersey": "21", "rating": 7.4, "pos": "LB", "photo": "", "age": "27", "val": "€30M", "height": "188 cm", "sofa_id": "867258"},
        {"name": "W. Endo", "jersey": "6", "rating": 7.6, "pos": "RDM", "photo": "", "age": "33", "val": "€13M", "height": "178 cm", "sofa_id": "232470"},
        {"name": "H. Morita", "jersey": "5", "rating": 7.5, "pos": "LDM", "photo": "", "age": "31", "val": "€15M", "height": "177 cm", "sofa_id": "866504"},
        {"name": "R. Doan", "jersey": "8", "rating": 7.5, "pos": "RAM", "photo": "", "age": "27", "val": "€18M", "height": "172 cm", "sofa_id": "826724"},
        {"name": "T. Minamino", "jersey": "10", "rating": 7.7, "pos": "CAM", "photo": "", "age": "31", "val": "€20M", "height": "174 cm", "sofa_id": "232471"},
        {"name": "K. Mitoma", "jersey": "7", "rating": 8.2, "pos": "LAM", "photo": "", "age": "29", "val": "€45M", "height": "178 cm", "sofa_id": "863212"},
        {"name": "A. Ueda", "jersey": "9", "rating": 7.3, "pos": "ST", "photo": "", "age": "27", "val": "€8M", "height": "182 cm", "sofa_id": "886367"},
    ],
    "portugal": [
        {"name": "Diogo Costa", "jersey": "22", "rating": 7.4, "pos": "GK", "photo": "", "age": "26", "val": "€45M", "height": "186 cm", "sofa_id": "852504"},
        {"name": "João Cancelo", "jersey": "20", "rating": 7.5, "pos": "RB", "photo": "", "age": "32", "val": "€25M", "height": "182 cm", "sofa_id": "832367"},
        {"name": "Rúben Dias", "jersey": "4", "rating": 7.8, "pos": "RCB", "photo": "frontend/assets/dias.png", "age": "29", "val": "€80M", "height": "187 cm", "sofa_id": "830225"},
        {"name": "Pepe", "jersey": "3", "rating": 7.2, "pos": "LCB", "photo": "", "age": "43", "val": "€1M", "height": "188 cm", "sofa_id": "11797"},
        {"name": "Nuno Mendes", "jersey": "19", "rating": 7.6, "pos": "LB", "photo": "", "age": "23", "val": "€55M", "height": "176 cm", "sofa_id": "966835"},
        {"name": "João Palhinha", "jersey": "6", "rating": 7.5, "pos": "RDM", "photo": "", "age": "30", "val": "€50M", "height": "190 cm", "sofa_id": "341499"},
        {"name": "Vitinha", "jersey": "23", "rating": 7.9, "pos": "LDM", "photo": "", "age": "26", "val": "€55M", "height": "172 cm", "sofa_id": "967268"},
        {"name": "Bernardo Silva", "jersey": "10", "rating": 8.0, "pos": "RAM", "photo": "frontend/assets/silva.png", "age": "31", "val": "€70M", "height": "173 cm", "sofa_id": "244465"},
        {"name": "Bruno Fernandes", "jersey": "8", "rating": 8.3, "pos": "CAM", "photo": "", "age": "31", "val": "€70M", "height": "179 cm", "sofa_id": "155029"},
        {"name": "Rafael Leão", "jersey": "17", "rating": 8.1, "pos": "LAM", "photo": "", "age": "26", "val": "€75M", "height": "188 cm", "sofa_id": "833099"},
        {"name": "C. Ronaldo", "jersey": "7", "rating": 8.2, "pos": "ST", "photo": "", "age": "41", "val": "€15M", "height": "187 cm", "sofa_id": "222"},
    ],
    "argentina": [
        {"name": "G. Rulli", "jersey": "12", "rating": 6.8, "pos": "GK", "photo": "", "age": "34", "val": "€4M", "height": "189 cm", "sofa_id": "155427", "sub": False},
        {"name": "F. Medina", "jersey": "25", "rating": 6.7, "pos": "LB", "photo": "", "age": "27", "val": "€22M", "height": "184 cm", "sofa_id": "935560", "sub": False},
        {"name": "L. Martínez", "jersey": "6", "rating": 7.0, "pos": "LCB", "photo": "", "age": "28", "val": "€45M", "height": "178 cm", "sofa_id": "867205", "sub": False},
        {"name": "N. Otamendi", "jersey": "19", "rating": 7.0, "pos": "RCB", "photo": "", "age": "38", "val": "€1.5M", "height": "183 cm", "sofa_id": "47355", "sub": False},
        {"name": "A. Giay", "jersey": "28", "rating": 7.2, "pos": "RB", "photo": "", "age": "21", "val": "€8M", "height": "180 cm", "sofa_id": "1110091", "sub": False},
        {"name": "V. Barco", "jersey": "8", "rating": 7.8, "pos": "LM", "photo": "", "age": "21", "val": "€9M", "height": "172 cm", "sofa_id": "1018596", "sub": False},
        {"name": "E. Palacios", "jersey": "14", "rating": 7.0, "pos": "LCM", "photo": "", "age": "27", "val": "€40M", "height": "177 cm", "sofa_id": "831626", "sub": False},
        {"name": "G. Lo Celso", "jersey": "11", "rating": 7.0, "pos": "RCM", "photo": "", "age": "30", "val": "€16M", "height": "177 cm", "sofa_id": "349479", "sub": False},
        {"name": "G. Simeone", "jersey": "17", "rating": 6.5, "pos": "RM", "photo": "", "age": "23", "val": "€10M", "height": "180 cm", "sofa_id": "1023773", "sub": False},
        {"name": "J. López", "jersey": "21", "rating": 6.8, "pos": "LST", "photo": "", "age": "25", "val": "€15M", "height": "188 cm", "sofa_id": "1026027", "sub": False},
        {"name": "N. Paz", "jersey": "18", "rating": 6.9, "pos": "RST", "photo": "", "age": "21", "val": "€10M", "height": "186 cm", "sofa_id": "1085352", "sub": False},
        # Substitutes
        {"name": "Cristian Romero", "jersey": "13", "rating": 6.7, "pos": "RCB", "photo": "", "age": "28", "val": "€60M", "height": "185 cm", "sofa_id": "865063", "sub": True},
        {"name": "Enzo Fernández", "jersey": "24", "rating": 6.8, "pos": "CM", "photo": "", "age": "25", "val": "€75M", "height": "178 cm", "sofa_id": "966236", "sub": True},
        {"name": "Rodrigo De Paul", "jersey": "7", "rating": 7.7, "pos": "RCM", "photo": "", "age": "32", "val": "€30M", "height": "180 cm", "sofa_id": "233054", "sub": True},
        {"name": "Alexis Mac Allister", "jersey": "20", "rating": 6.9, "pos": "LCM", "photo": "", "age": "27", "val": "€75M", "height": "176 cm", "sofa_id": "868357", "sub": True},
        {"name": "Lautaro Martínez", "jersey": "22", "rating": 7.3, "pos": "ST", "photo": "", "age": "28", "val": "€110M", "height": "174 cm", "sofa_id": "830206", "sub": True},
        {"name": "Thiago Almada", "jersey": "16", "rating": 7.7, "pos": "CAM", "photo": "", "age": "25", "val": "€27M", "height": "171 cm", "sofa_id": "925345", "sub": True},
        {"name": "Nicolás González", "jersey": "15", "rating": 6.5, "pos": "LM", "photo": "", "age": "28", "val": "€35M", "height": "180 cm", "sofa_id": "828236", "sub": True},
        {"name": "Gonzalo Montiel", "jersey": "4", "rating": 6.8, "pos": "RB", "photo": "", "age": "29", "val": "€10M", "height": "175 cm", "sofa_id": "831548", "sub": True},
        {"name": "Lionel Messi", "jersey": "10", "rating": 7.7, "pos": "ST", "photo": "", "age": "38", "val": "€30M", "height": "170 cm", "sofa_id": "206", "sub": True}
    ],
    "iceland": [
        {"name": "E. Ólafsson", "jersey": "1", "rating": 6.9, "pos": "GK", "photo": "", "age": "26", "val": "€1M", "height": "201 cm", "sofa_id": "964344", "sub": False},
        {"name": "L. Tómasson", "jersey": "2", "rating": 6.6, "pos": "LB", "photo": "", "age": "27", "val": "€800K", "height": "183 cm", "sofa_id": "865769", "sub": False},
        {"name": "H. Magnússon", "jersey": "23", "rating": 6.1, "pos": "LCB", "photo": "", "age": "33", "val": "€1.2M", "height": "190 cm", "sofa_id": "117973", "sub": False},
        {"name": "D. Grétarsson", "jersey": "3", "rating": 6.1, "pos": "RCB", "photo": "", "age": "30", "val": "€500K", "height": "185 cm", "sofa_id": "263590", "sub": False},
        {"name": "V. Pálsson", "jersey": "4", "rating": 6.3, "pos": "RB", "photo": "", "age": "35", "val": "€400K", "height": "186 cm", "sofa_id": "45664", "sub": False},
        {"name": "M. Ellertsson", "jersey": "19", "rating": 6.3, "pos": "LM", "photo": "", "age": "24", "val": "€2.5M", "height": "182 cm", "sofa_id": "966456", "sub": False},
        {"name": "Í. B. Jóhannesson", "jersey": "8", "rating": 6.4, "pos": "LCM", "photo": "", "age": "23", "val": "€3.5M", "height": "180 cm", "sofa_id": "951952", "sub": False},
        {"name": "A. Baldursson", "jersey": "14", "rating": 6.4, "pos": "RCM", "photo": "", "age": "24", "val": "€800K", "height": "183 cm", "sofa_id": "926252", "sub": False},
        {"name": "A. Guðmundsson", "jersey": "11", "rating": 7.0, "pos": "RM", "photo": "", "age": "28", "val": "€22M", "height": "177 cm", "sofa_id": "826388", "sub": False},
        {"name": "H. Haraldsson", "jersey": "7", "rating": 6.4, "pos": "LST", "photo": "", "age": "23", "val": "€15M", "height": "180 cm", "sofa_id": "994468", "sub": False},
        {"name": "O. S. Óskarsson", "jersey": "9", "rating": 6.5, "pos": "RST", "photo": "", "age": "21", "val": "€5M", "height": "186 cm", "sofa_id": "1012975", "sub": False},
        # Substitutes
        {"name": "Kristian Hlynsson", "jersey": "20", "rating": 6.1, "pos": "CAM", "photo": "", "age": "22", "val": "€5M", "height": "179 cm", "sofa_id": "966453", "sub": True},
        {"name": "Dagur Dan Þórhallsson", "jersey": "15", "rating": 5.9, "pos": "LB", "photo": "", "age": "26", "val": "€1M", "height": "178 cm", "sofa_id": "926251", "sub": True},
        {"name": "Aron Gunnarsson", "jersey": "17", "rating": 6.3, "pos": "CM", "photo": "", "age": "37", "val": "€300K", "height": "177 cm", "sofa_id": "44738", "sub": True},
        {"name": "Jón Dagur Þorsteinsson", "jersey": "18", "rating": 7.0, "pos": "LM", "photo": "", "age": "27", "val": "€3M", "height": "178 cm", "sofa_id": "837269", "sub": True},
        {"name": "Hjörtur Hermannsson", "jersey": "6", "rating": 6.3, "pos": "RCB", "photo": "", "age": "30", "val": "€800K", "height": "188 cm", "sofa_id": "260021", "sub": True},
        {"name": "Gísli Þórðarson", "jersey": "5", "rating": 6.3, "pos": "RCM", "photo": "", "age": "24", "val": "€300K", "height": "180 cm", "sofa_id": "964343", "sub": True},
        {"name": "Kristall Máni Ingason", "jersey": "16", "rating": 6.4, "pos": "ST", "photo": "", "age": "24", "val": "€500K", "height": "180 cm", "sofa_id": "994467", "sub": True},
        {"name": "Arnór Sigurðsson", "jersey": "21", "rating": 6.4, "pos": "LM", "photo": "", "age": "26", "val": "€3M", "height": "177 cm", "sofa_id": "865767", "sub": True},
        {"name": "Gylfi Sigurðsson", "jersey": "10", "rating": 6.6, "pos": "CAM", "photo": "", "age": "36", "val": "€500K", "height": "186 cm", "sofa_id": "44722", "sub": True}
    ]
}


def normalize_name(name: str) -> str:
    """Normalizes team names to lower case, stripping spaces, extra qualifiers like U20, and accents."""
    import unicodedata
    n = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
    n = n.lower().strip()
    n = re.sub(r"\s+u\d+\b", "", n)
    n = re.sub(r"\s+u-\d+\b", "", n)
    return n

def load_cache() -> Dict[str, List[Dict[str, Any]]]:
    lock_path = CACHE_PATH.with_suffix(".lock")
    if not lock_path.exists():
        try:
            lock_path.touch()
        except Exception:
            pass
    try:
        with open(lock_path, "r") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_SH)
            if CACHE_PATH.exists():
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception as e:
        logger.error(f"Error loading roster cache from {CACHE_PATH}: {e}")
    return {}

def save_cache(cache: Dict[str, List[Dict[str, Any]]]) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = CACHE_PATH.with_suffix(".lock")
        with open(lock_path, "w") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving roster cache to {CACHE_PATH}: {e}")

def slugify(name: str) -> str:
    # Remove non-alphanumeric characters and replace spaces/hyphens with underscores
    name_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    return re.sub(r'[\s-]+', '_', name_clean).lower()

NAME_EXPANSIONS = {
    # Manchester City
    "K. Walker": "Kyle Walker",
    "R. Dias": "Rúben Dias",
    "M. Akanji": "Manuel Akanji",
    "J. Gvardiol": "Joško Gvardiol",
    "J. Stones": "John Stones",
    "B. Silva": "Bernardo Silva",
    "K. De Bruyne": "Kevin De Bruyne",
    "P. Foden": "Phil Foden",
    "E. Haaland": "Erling Haaland",
    
    # Real Madrid
    "A. Lunin": "Andriy Lunin",
    "D. Carvajal": "Daniel Carvajal",
    "A. Rüdiger": "Antonio Rüdiger",
    "F. Mendy": "Ferland Mendy",
    "F. Valverde": "Federico Valverde",
    "T. Kroos": "Toni Kroos",
    "E. Camavinga": "Eduardo Camavinga",
    "J. Bellingham": "Jude Bellingham",
    "Vinícius Jr.": "Vinícius Júnior",
    
    # Bayern
    "M. Neuer": "Manuel Neuer",
    "J. Kimmich": "Joshua Kimmich",
    "M. de Ligt": "Matthijs de Ligt",
    "E. Dier": "Eric Dier",
    "N. Mazraoui": "Noussair Mazraoui",
    "K. Laimer": "Konrad Laimer",
    "A. Pavlović": "Aleksandar Pavlović",
    "L. Sané": "Leroy Sané",
    "T. Müller": "Thomas Müller",
    "J. Musiala": "Jamal Musiala",
    "H. Kane": "Harry Kane",
    
    # Arsenal
    "D. Raya": "David Raya",
    "B. White": "Ben White",
    "W. Saliba": "William Saliba",
    "G. Magalhães": "Gabriel Magalhães",
    "J. Kiwior": "Jakub Kiwior",
    "D. Rice": "Declan Rice",
    "M. Ødegaard": "Martin Ødegaard",
    "B. Saka": "Bukayo Saka",
    "G. Martinelli": "Gabriel Martinelli",
    "K. Havertz": "Kai Havertz",
    
    # Haiti
    "L. Joseph": "Leonel Joseph",
    "R. Providence": "Ruben Providence",
    "F. Pierrot": "Frantzdy Pierrot",
    
    # Spain
    "U. Simón": "Unai Simón",
    "M. Llorente": "Marcos Llorente",
    "P. Cubarsí": "Pau Cubarsí",
    "A. Laporte": "Aymeric Laporte",
    "M. Cucurella": "Marc Cucurella",
    "A. Baena": "Alex Baena",
    "F. Ruiz": "Fabian Ruiz",
    "F. Torres": "Ferran Torres",
    "M. Oyarzabal": "Mikel Oyarzabal",
    
    # Peru
    "P. Gallese": "Pedro Gallese",
    "R. Garces": "Renzo Garcés",
    "F. Gruber": "Franz Gruber",
    "O. Sonne": "Oliver Sonne",
    "J. Pretell": "Jesús Pretell",
    "E. Noriega": "Erick Noriega",
    "J. Vélez": "Jairo Vélez",
    "Y. Yotún": "Yoshimar Yotún",
    "M. López": "Marcos López",
    "A. Ugarriza": "Adrián Ugarriza",
    
    # Liverpool
    "Alisson B.": "Alisson Becker",
    "I. Konaté": "Ibrahima Konaté",
    "V. van Dijk": "Virgil van Dijk",
    "A. Robertson": "Andrew Robertson",
    "W. Endo": "Wataru Endo",
    "L. Díaz": "Luis Díaz",
    "D. Núñez": "Darwin Núñez",
    
    # Philippines
    "N. Etheridge": "Neil Etheridge",
    "C. de Murga": "Carli de Murga",
    "A. Aguinaldo": "Amani Aguinaldo",
    "C. Rontini": "Christian Rontini",
    "D. Sato": "Daisuke Sato",
    "K. Ingreso": "Kevin Ingreso",
    "S. Schröck": "Stephan Schröck",
    "P. Reichelt": "Patrick Reichelt",
    
    # Guam
    "D. Jaye": "Dallas Jaye",
    "T. Nicklaw": "Travis Nicklaw",
    "M. Grimes": "Marcus Grimes",
    "J. Grindeland": "Joey Grindeland",
    "M. Chargualaf": "Mark Chargualaf",
    "I. Mariano": "Ian Mariano",
    "M. Lopez": "Marcus Lopez",
    "J. Cunliffe": "Jason Cunliffe",
    "S. Spindel": "Shawn Spindel",
    "S. Malcolm": "Shane Malcolm",
    
    # Japan
    "Z. Suzuki": "Zion Suzuki",
    "Y. Sugawara": "Yukinari Sugawara",
    "K. Itakura": "Ko Itakura",
    "K. Machida": "Koki Machida",
    "H. Ito": "Hiroki Ito",
    "H. Morita": "Hidemasa Morita",
    "R. Doan": "Ritsu Doan",
    "T. Minamino": "Takumi Minamino",
    "K. Mitoma": "Kaoru Mitoma",
    "A. Ueda": "Ayase Ueda",
    
    # Portugal
    "C. Ronaldo": "Cristiano Ronaldo",
    
    # Argentina
    "G. Rulli": "Gerónimo Rulli",
    "F. Medina": "Facundo Medina",
    "L. Martínez": "Lisandro Martínez",
    "N. Otamendi": "Nicolás Otamendi",
    "A. Giay": "Agustín Giay",
    "V. Barco": "Valentín Barco",
    "E. Palacios": "Exequiel Palacios",
    "G. Lo Celso": "Giovani Lo Celso",
    "G. Simeone": "Giuliano Simeone",
    "J. López": "José Manuel López",
    "N. Paz": "Nico Paz",
    
    # Iceland
    "E. Ólafsson": "Elías Ólafsson",
    "L. Tómasson": "Logi Tómasson",
    "H. Magnússon": "Hörður Magnússon",
    "D. Grétarsson": "Daníel Grétarsson",
    "V. Pálsson": "Victor Pálsson",
    "M. Ellertsson": "Mikael Egill Ellertsson",
    "Í. B. Jóhannesson": "Ísak Bergmann Jóhannesson",
    "A. Baldursson": "Andri Baldursson",
    "A. Guðmundsson": "Albert Guðmundsson",
    "H. Haraldsson": "Hákon Arnar Haraldsson",
    "O. S. Óskarsson": "Orri Óskarsson",
    "Dagur Dan Þórhallsson": "Dagur Thórhallsson",
    "Jón Dagur Þorsteinsson": "Jón Thorsteinsson",
    "Kristall Máni Ingason": "Kristall Ingason",
    "Manny Ott": "Manuel Ott",
    "OJ Porteria": "José Porteria",
}

TRANSFERMARKT_BLOCKED = False
WIKIPEDIA_BLOCKED = False

def fetch_wikipedia_image_url(player_name: str) -> Optional[str]:
    global WIKIPEDIA_BLOCKED
    if WIKIPEDIA_BLOCKED:
        return None
    headers = {'User-Agent': 'FootBotTacticsApp/1.0 (akilan@example.com)'}
    search_url = 'https://en.wikipedia.org/w/api.php'
    
    # Expand name to full canonical format for searching if applicable
    search_name = NAME_EXPANSIONS.get(player_name, player_name)
    
    # Try search queries in order of specificity
    queries = [f"{search_name} football", f"{search_name} footballer", search_name]
    
    for q in queries:
        search_params = {
            'action': 'opensearch',
            'search': q,
            'limit': 5, # Check up to 5 results to ensure we don't miss the real player
            'format': 'json'
        }
        try:
            r = requests.get(search_url, params=search_params, headers=headers, timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                if len(data) >= 2 and data[1]:
                    # Check first few search results
                    for title in data[1]:
                        # Query both extracts and pageimages to verify article category & get thumbnail
                        info_params = {
                            'action': 'query',
                            'titles': title,
                            'prop': 'extracts|pageimages',
                            'exintro': True,
                            'explaintext': True,
                            'format': 'json',
                            'pithumbsize': 500
                        }
                        r_info = requests.get(search_url, params=info_params, headers=headers, timeout=2.0)
                        if r_info.status_code == 200:
                            pages = r_info.json().get('query', {}).get('pages', {})
                            for pid, pinfo in pages.items():
                                extract_text = pinfo.get('extract', '').lower()
                                
                                # Verify if the article is actually about a football player/coach or sport team/club
                                is_football = False
                                football_keywords = [
                                    "footballer", "football player", "soccer player", "fútbol", 
                                    "futbolista", "goalkeeper", "midfielder", "defender", "striker", 
                                    "winger", "forward", "football club", "national football team"
                                ]
                                for kw in football_keywords:
                                    if kw in extract_text:
                                        is_football = True
                                        break
                                
                                # Fallback sports keywords
                                if not is_football:
                                    fallback_keywords = [
                                        "plays as a", "caps for", "represented his country", 
                                        "association football", "national team"
                                    ]
                                    for kw in fallback_keywords:
                                        if kw in extract_text:
                                            is_football = True
                                            break
                                
                                # Only accept the thumbnail if it is a verified sports entity
                                if is_football and 'thumbnail' in pinfo:
                                    return pinfo['thumbnail']['source']
        except requests.exceptions.Timeout:
            logger.error(f"Wikipedia request timed out for {q}. Tripping circuit breaker to prevent cascading timeouts.")
            WIKIPEDIA_BLOCKED = True
            break
        except Exception as e:
            logger.error(f"Error searching Wikipedia for {q}: {e}")
            
    return None

def fetch_transfermarkt_image_url(player_name: str) -> Optional[str]:
    global TRANSFERMARKT_BLOCKED
    if TRANSFERMARKT_BLOCKED:
        return None
        
    import urllib.parse
    from bs4 import BeautifulSoup
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    # Expand player name if abbreviated
    search_name = NAME_EXPANSIONS.get(player_name, player_name)
    query = urllib.parse.quote_plus(search_name)
    url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={query}"
    
    try:
        r = requests.get(url, headers=headers, timeout=2.0)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            # Look for player search result table
            table = soup.find('table', class_='items')
            if table:
                tbody = table.find('tbody')
                if tbody:
                    first_row = tbody.find('tr', class_=['odd', 'even'])
                    if first_row:
                        img_tag = first_row.find('img')
                        if img_tag and img_tag.get('src'):
                            src = img_tag.get('src')
                            # Ensure we don't return blank placeholder images
                            if "placeholder" not in src:
                                return src
    except requests.exceptions.Timeout:
        logger.error(f"Transfermarkt request timed out for {player_name}. Tripping circuit breaker to prevent cascading timeouts.")
        TRANSFERMARKT_BLOCKED = True
    except Exception as e:
        logger.error(f"Error fetching Transfermarkt image for {player_name}: {e}")
    return None

def download_image(url: str, dest_path: Path) -> bool:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, load_image_fail_check_bypass) Chrome/115.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            logger.info(f"Successfully downloaded player photo to {dest_path}")
            return True
    except Exception as e:
        logger.error(f"Failed to download image from {url} to {dest_path}: {e}")
    return False

def clean_text(text: str) -> str:
    """Removes accents, lowercases, and strips non-alphanumeric chars for matching."""
    text_unicode = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text_unicode).lower().strip()
    return re.sub(r'\s+', ' ', text_clean)

def clean_special_chars(input_str: str) -> str:
    # Handle specific Icelandic characters and other non-standard chars
    s = input_str.replace('ð', 'd').replace('Ð', 'D')
    s = s.replace('þ', 'th').replace('Þ', 'Th')
    s = s.replace('æ', 'ae').replace('Æ', 'Ae')
    return clean_text(s)

def resolve_fotmob_id(player_name: str, team_name: str = "") -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    # Expand name
    search_name = NAME_EXPANSIONS.get(player_name, player_name)
    
    # Try different query options
    queries = [search_name, clean_special_chars(search_name), clean_special_chars(player_name)]
    
    for query in queries:
        if not query:
            continue
        url = f"https://apigw.fotmob.com/searchapi/suggest?term={urllib.parse.quote_plus(query)}&lang=en"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                options = []
                for val in data.values():
                    if isinstance(val, list):
                        for group in val:
                            if isinstance(group, dict) and "options" in group:
                                options.extend(group["options"])
                
                if not options:
                    continue
                    
                target_clean = clean_text(search_name)
                
                best_opt = None
                best_match_level = 0 # 0=none, 1=partial name, 2=exact name, 3=exact name + team
                
                for opt in options:
                    payload = opt.get("payload", {})
                    pid = payload.get("id")
                    if not pid:
                        continue
                        
                    opt_name = opt.get("text", "").split("|")[0]
                    opt_name_clean = clean_text(opt_name)
                    opt_team = payload.get("teamName", "")
                    
                    match_level = 0
                    if opt_name_clean == target_clean:
                        match_level = 2
                        if team_name and clean_text(team_name) in clean_text(opt_team):
                            match_level = 3
                    elif target_clean in opt_name_clean or opt_name_clean in target_clean:
                        match_level = 1
                    
                    if match_level > best_match_level:
                        best_match_level = match_level
                        best_opt = opt
                    elif match_level == best_match_level and best_opt:
                        if opt.get("score", 0) > best_opt.get("score", 0):
                            best_opt = opt
                            
                if best_opt:
                    return best_opt.get("payload", {}).get("id", "")
        except Exception as e:
            logger.error(f"Error resolving FotMob ID for {player_name} with query '{query}': {e}")
            
    return ""

def ensure_player_photos(roster: List[Dict[str, Any]], team_name: str = "") -> bool:
    """
    Checks each player in the roster and resolves their photo path.
    First tries to resolve via FotMob ID and download from FotMob CDN.
    If that fails, queries Transfermarkt, falling back to Wikipedia.
    Returns True if any player's photo was updated.
    """
    updated = False
    base_dir = Path(__file__).resolve().parent.parent
    assets_dir = base_dir / "frontend" / "assets"
    
    for p in roster:
        player_name = p["name"]
        slug = slugify(player_name)
        
        # Check if the PNG file already exists locally from a previous download
        dest_filename_png = f"{slug}.png"
        dest_path_png = assets_dir / dest_filename_png
        relative_path_png = f"frontend/assets/{dest_filename_png}"
        
        if dest_path_png.exists():
            if p.get("photo") != relative_path_png:
                p["photo"] = relative_path_png
                updated = True
            continue
            
        logger.info(f"Attempting to resolve FotMob photo for {player_name}...")
        fotmob_id = resolve_fotmob_id(player_name, team_name)
        download_success = False
        if fotmob_id:
            fotmob_url = f"https://images.fotmob.com/image_resources/playerimages/{fotmob_id}.png"
            if download_image(fotmob_url, dest_path_png):
                p["photo"] = relative_path_png
                updated = True
                download_success = True
                
        if download_success:
            continue
            
        # Fallback to existing JPG check or Transfermarkt/Wikipedia
        dest_filename_jpg = f"{slug}.jpg"
        dest_path_jpg = assets_dir / dest_filename_jpg
        relative_path_jpg = f"frontend/assets/{dest_filename_jpg}"
        
        if dest_path_jpg.exists():
            if p.get("photo") != relative_path_jpg:
                p["photo"] = relative_path_jpg
                updated = True
            continue
            
        logger.info(f"FotMob photo not resolved for {player_name}, trying Transfermarkt...")
        url = fetch_transfermarkt_image_url(player_name)
        
        if not url:
            logger.info(f"Transfermarkt photo not resolved for {player_name}, trying Wikipedia...")
            url = fetch_wikipedia_image_url(player_name)
            
        if url:
            if download_image(url, dest_path_jpg):
                p["photo"] = relative_path_jpg
                updated = True
            else:
                p["photo"] = "none"
                updated = True
        else:
            p["photo"] = "none"
            updated = True
            
    return updated

def get_real_world_roster(team_name: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns the real-world starting XI squad for a team.
    Checks predefined list first, then local cache, and finally queries LLM if key is available.
    """
    norm_name = normalize_name(team_name)
    logger.info(f"Resolving real-world roster for: '{team_name}' (normalized: '{norm_name}')")

    # 1. Predefined list match checks
    predefined_val = None
    for k, v in PREDEFINED_ROSTERS.items():
        if k == norm_name or k in norm_name or norm_name in k:
            logger.info(f"Roster for '{team_name}' found in PREDEFINED_ROSTERS under '{k}'")
            predefined_val = v
            break

    # 2. Local cache lookup
    cache = load_cache()
    if norm_name in cache:
        logger.info(f"Roster for '{team_name}' found in local cache.")
        roster = cache[norm_name]
        
        # Enrich cached roster with sofa_id from PREDEFINED_ROSTERS if available
        matching_predefined = None
        for k, v in PREDEFINED_ROSTERS.items():
            if k == norm_name or k in norm_name or norm_name in k:
                matching_predefined = v
                break
        
        cache_updated = False
        if matching_predefined:
            predefined_map = {normalize_name(p["name"]): p.get("sofa_id", "") for p in matching_predefined}
            for p in roster:
                norm_p_name = normalize_name(p["name"])
                if "sofa_id" not in p or (not p["sofa_id"] and predefined_map.get(norm_p_name)):
                    p["sofa_id"] = predefined_map.get(norm_p_name, "")
                    cache_updated = True
                    
        updated_photos = ensure_player_photos(roster, team_name)
        if cache_updated or updated_photos:
            current_cache = load_cache()
            current_cache[norm_name] = roster
            save_cache(current_cache)
        return roster

    if predefined_val is not None:
        import copy
        roster = copy.deepcopy(predefined_val)
        ensure_player_photos(roster, team_name)
        current_cache = load_cache()
        current_cache[norm_name] = roster
        save_cache(current_cache)
        return roster

    # 3. LLM Query if OpenAI is initialized
    if rag_engine.openai_client is not None:
        logger.info(f"Roster for '{team_name}' not found in cache. Querying LLM...")
        
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
- 'sofa_id': The player's official numerical Sofascore player ID as a string if known (e.g. '826725' for Erling Haaland, '40387' for Kevin De Bruyne). Guess a highly realistic numerical ID if you know it, otherwise return empty string "".

Return ONLY a raw valid JSON array. Do not write any markdown code wrappers (like ```json), notes, explanations, or extra characters. Simply return the raw JSON text. Make sure to double check that you are returning EXACTLY 11 players."""

        for attempt in range(1, 4):
            try:
                completion = rag_engine.openai_client.chat.completions.create(
                    model=rag_engine.model_name,
                    messages=[
                        {"role": "system", "content": "You are a database system returning raw JSON arrays only. Double check that you output exactly 11 players, one of which has position 'GK'."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3 + (attempt * 0.1)
                )
                response_text = completion.choices[0].message.content.strip()
                
                # Clean markdown wrappers if any
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                try:
                    roster = json.loads(response_text)
                except Exception as json_err:
                    logger.warning(f"Standard json.loads failed on attempt {attempt}: {json_err}. Attempting cleaning and ast.literal_eval...")
                    import ast
                    cleaned_text = response_text
                    # strip markdown wrappers
                    cleaned_text = re.sub(r"^```json\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
                    cleaned_text = cleaned_text.strip()
                    # Replace JSON literals with Python equivalents
                    cleaned_text = cleaned_text.replace("true", "True").replace("false", "False").replace("null", "None")
                    try:
                        roster = ast.literal_eval(cleaned_text)
                    except Exception as ast_err:
                        logger.error(f"ast.literal_eval also failed on attempt {attempt}: {ast_err}")
                        raise json_err
                
                if isinstance(roster, list) and len(roster) == 11:
                    # Validate structures
                    valid = True
                    required_keys = {"name", "jersey", "rating", "pos", "photo", "age", "val", "height", "sofa_id"}
                    for p in roster:
                        if not required_keys.issubset(p.keys()):
                            valid = False
                            break
                    
                    if valid:
                        logger.info(f"Successfully retrieved and validated LLM roster for '{team_name}' on attempt {attempt}. Caching...")
                        ensure_player_photos(roster, team_name)
                        current_cache = load_cache()
                        current_cache[norm_name] = roster
                        save_cache(current_cache)
                        return roster
                    else:
                        logger.warning(f"Attempt {attempt}: LLM returned JSON list but it was missing required player keys.")
                else:
                    logger.warning(f"Attempt {attempt}: LLM did not return exactly 11 players. Length: {len(roster) if isinstance(roster, list) else 'not a list'}")
                
            except Exception as e:
                logger.error(f"Attempt {attempt} failed to query LLM for roster: {e}")
            
            if attempt < 3:
                import time
                time.sleep(1.5)
    else:
        logger.warning("OpenAI client not initialized. Cannot fetch roster via LLM.")

    return None

