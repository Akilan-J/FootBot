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

def normalize_date_string(date_str: str) -> str:
    """Extracts only the date portion from a match date string (e.g. '14 Jun 2026 - Group E' -> '14 jun 2026')"""
    if not date_str:
        return ""
    # Try to find date patterns like DD MMM YYYY (e.g. 14 Jun 2026)
    match = re.search(r"\b\d{1,2}\s+[a-zA-Z]{3}\s+\d{4}\b", date_str)
    if match:
        return match.group(0).lower().strip()
    # Try to find date patterns like YYYY-MM-DD (e.g. 2026-06-10)
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", date_str)
    if match:
        return match.group(0).lower().strip()
    # Otherwise split by " - " or "@" and take the first part
    parts = re.split(r"\s+[-@]\s+", date_str)
    res = parts[0].lower().strip()
    if res == "today":
        import datetime
        return datetime.date.today().strftime("%d %b %Y").lower()
    return res

def _clean_yahoo_url(url: str) -> str:
    """Decodes Yahoo search redirect URLs to direct target URLs."""
    if "r.search.yahoo.com" in url and "/RU=" in url:
        try:
            import urllib.parse
            parts = url.split("/RU=")
            if len(parts) > 1:
                target = parts[1].split("/RK=")[0] if "/RK=" in parts[1] else parts[1].split("/")[0]
                return urllib.parse.unquote(target)
        except Exception:
            pass
    return url


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

def get_real_world_roster(
    team_name: str,
    opponent_name: Optional[str] = None,
    match_date: Optional[str] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns the real-world starting XI squad for a team.
    If opponent_name and match_date are provided, resolves the match-specific starting XI.
    """
    norm_name = normalize_name(team_name)

    # 1. Match-specific cache lookup
    match_key = None
    if opponent_name and match_date:
        norm_opp = normalize_name(opponent_name)
        # Resolve "Today" or "Today @ HH:MM IST" to the actual calendar date
        resolved_match_date = match_date
        if resolved_match_date.lower().startswith("today"):
            import datetime
            resolved_match_date = datetime.date.today().strftime("%d %b %Y")
        norm_date = normalize_date_string(resolved_match_date)
        match_key = f"{norm_name}_vs_{norm_opp}_{norm_date}"
        
        cache = load_cache()
        roster = None
        if match_key in cache:
            roster = cache[match_key]
        else:
            # Fallback for predefined "_today" keys
            if "today" in match_date.lower():
                today_key = f"{norm_name}_vs_{norm_opp}_today"
                if today_key in cache:
                    roster = cache[today_key]
                    
        if roster is not None:
            logger.info(f"Roster for '{team_name}' vs '{opponent_name}' ({match_date}) found in cache.")
            updated_photos = ensure_player_photos(roster, team_name)
            if updated_photos:
                current_cache = load_cache()
                current_cache[match_key] = roster
                save_cache(current_cache)
            return roster

    # 2. Match-specific search-grounded LLM query
    if match_key and rag_engine.openai_client is not None:
        logger.info(f"Match-specific roster for '{team_name}' vs '{opponent_name}' ({match_date}) not in cache. Querying web search & LLM...")
        resolved_date = match_date
        if "today" in match_date.lower():
            import datetime
            resolved_date = datetime.date.today().strftime("%d %b %Y")
            
        # Standardize month names to full format for better indexing
        search_date = resolved_date
        month_map = {
            "jan": "January", "feb": "February", "mar": "March", "apr": "April",
            "may": "May", "jun": "June", "jul": "July", "aug": "August",
            "sep": "September", "oct": "October", "nov": "November", "dec": "December"
        }
        for k, v in month_map.items():
            if k in search_date.lower():
                search_date = re.sub(k, v, search_date, flags=re.IGNORECASE)
                break
                
        # Combine multiple search queries to bypass Yahoo 500 errors and gather rich context
        q1 = f"{team_name} vs {opponent_name} {search_date} starting XI"
        q2 = f"{team_name} vs {opponent_name} {search_date} lineups"
        
        search_results = []
        try:
            r1 = rag_engine.web_search_fallback(q1, max_results=3, clean=False)
            r2 = rag_engine.web_search_fallback(q2, max_results=3, clean=False)
            
            # Combine results, removing duplicates by href
            seen = set()
            for r in r1 + r2:
                href = r.get("href", "")
                if href and href in seen:
                    continue
                if href:
                    seen.add(href)
                search_results.append(r)
        except Exception as e:
            logger.error(f"Web search fallback failed: {e}")
            
        search_context = ""
        if search_results:
            search_context_parts = []
            for r in search_results:
                search_context_parts.append(f"- {r['title']}: {r['body']}")
            
            # Fetch full page text for the top results to avoid LLM hallucinations
            fetched_count = 0
            for r in search_results:
                url = r.get("href", "")
                if url:
                    url = _clean_yahoo_url(url)
                if url and not any(loc in url for loc in ["localhost", "127.0.0.1"]):
                    # Skip general country/place pages that are not about the football match
                    url_lower = url.lower()
                    if "wikipedia.org/wiki/" in url_lower and any(c in url_lower for c in ["congo", "portugal", "spain", "peru", "angola", "japan", "iceland", "argentina", "germany", "france", "england", "belgium", "vietnam", "philippines", "guam"]):
                        continue
                    if "britannica.com" in url_lower:
                        continue
                        
                    logger.info(f"Fetching webpage content for RAG context: {url}")
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                        page_res = requests.get(url, headers=headers, timeout=5.0)
                        if page_res.status_code == 200:
                            from bs4 import BeautifulSoup
                            page_soup = BeautifulSoup(page_res.text, "html.parser")
                            for s in page_soup(["script", "style", "noscript", "header", "footer", "nav"]):
                                s.extract()
                            page_text = page_soup.get_text(separator=" ")
                            cleaned_page_text = " ".join([phrase.strip() for phrase in page_text.split() if phrase.strip()])
                            if len(cleaned_page_text) > 100:
                                search_context_parts.append(f"\n--- Full Page Content from {url} ---\n{cleaned_page_text[:6000]}")
                                fetched_count += 1
                                if fetched_count >= 2:
                                    break
                    except Exception as page_err:
                        logger.error(f"Failed to fetch content from {url}: {page_err}")
            
            search_context = "\n".join(search_context_parts)
            
        prompt = f"""You are a professional football database helper. Your job is to return the actual, real-world starting XI lineup AND substitutes squad for the football team '{team_name}' in their match against '{opponent_name}' played on '{resolved_date}'.
        
        Here is the search context about the match:
        {search_context}
        
        Using the search context above and your general football knowledge, return a list of players in the matchday team. This list MUST include:
        1. The 11 starting players who started the match.
        2. The substitutes/bench players (up to 7-10 main substitutes).
        
        CRITICAL RULES FOR LINEUP ACCURACY:
        1. Prioritize official, actual confirmed lineups and match reports over fantasy previews, predicted lineups, or pre-match articles.
        2. Any players mentioned as goalscorers, assisters, or key players in the match text (such as Yoane Wissa, João Neves, Cristiano Ronaldo, Pedro Neto, Arthur Masuaku) MUST be included in the starting XI if they started, or as substitutes if they were subbed in.
        3. Double check that the players are active in the year 2026 for their respective national teams.
        4. Ensure there are exactly 11 players with 'sub': false (representing the starting XI), and one of those starters must be a goalkeeper (pos: 'GK'). All other players should have 'sub': true.
        5. Each player must have exactly the following keys:
        - 'name': The real player's full name (e.g. 'Bukayo Saka' or 'A. Lunin')
        - 'jersey': Their squad/jersey number as a string (e.g. '7')
        - 'rating': A realistic SofaScore performance rating for this match as a float between 5.0 and 9.9 (e.g. 7.4)
        - 'pos': One of the standard tactical positions: 'GK', 'RB', 'RCB', 'LCB', 'LB', 'LDM', 'RDM', 'LCM', 'CM', 'RCM', 'LAM', 'CAM', 'RAM', 'LW', 'ST', 'RW', 'LST', 'RST', 'LM', 'RM', 'AM'.
        - 'photo': Always an empty string ""
        - 'age': The player's age as a string (e.g. '24')
        - 'val': The player's market value as a string (e.g. '€120M' or '€5M')
        - 'height': The player's height as a string (e.g. '178 cm')
        - 'sofa_id': The player's official numerical Sofascore player ID as a string if known, otherwise "".
        - 'sub': true if the player was a substitute (bench player) who did not start, false if they were in the starting XI.
        - 'subbed_in_for': If the player was a substitute and was subbed on to replace another player during the match (either a starter or another substitute), specify the exact name of the player they replaced. Otherwise, return null.
        - 'subbed_in_minute': If the player was subbed on, specify the minute of the substitution (e.g. "65'" or "89'"). Otherwise, return null.
        
        Return ONLY a raw valid JSON array. Do not write any markdown code wrappers, notes, explanations, or extra characters. Simply return the raw JSON text."""
        
        for attempt in range(1, 4):
            try:
                completion = rag_engine.openai_client.chat.completions.create(
                    model=rag_engine.model_name,
                    messages=[
                        {"role": "system", "content": "You are a database system returning raw JSON arrays only. Double check that you output exactly 11 starting players with 'sub': false and one has position 'GK'."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3 + (attempt * 0.1),
                    timeout=15.0
                )
                raw_content = completion.choices[0].message.content
                if not raw_content:
                    raw_content = getattr(completion.choices[0].message, 'reasoning', None) or ""
                response_text = raw_content.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                try:
                    roster = json.loads(response_text)
                except Exception as json_err:
                    import ast
                    cleaned_text = response_text
                    cleaned_text = re.sub(r"^```json\s*", "", cleaned_text)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
                    cleaned_text = cleaned_text.strip()
                    cleaned_text = cleaned_text.replace("true", "True").replace("false", "False").replace("null", "None")
                    try:
                        roster = ast.literal_eval(cleaned_text)
                    except Exception as ast_err:
                        raise json_err
                        
                if isinstance(roster, list) and len(roster) >= 11:
                    valid = True
                    required_keys = {"name", "jersey", "rating", "pos", "photo", "age", "val", "height", "sofa_id", "sub", "subbed_in_for", "subbed_in_minute"}
                    for p in roster:
                        # Backwards compatibility and default fields for safety
                        p["sub"] = p.get("sub", False)
                        p["subbed_in_for"] = p.get("subbed_in_for", None)
                        p["subbed_in_minute"] = p.get("subbed_in_minute", None)
                        if not {"name", "jersey", "rating", "pos", "photo", "age", "val", "height", "sofa_id"}.issubset(p.keys()):
                            valid = False
                            break
                    if valid:
                        # Post-process to ensure no player is subbed out more than twice
                        subbed_out_counts = {}
                        for p in roster:
                            if p.get("sub") and p.get("subbed_in_for"):
                                tgt = p["subbed_in_for"].strip().lower()
                                current_cnt = subbed_out_counts.get(tgt, 0)
                                if current_cnt >= 2:
                                    p["subbed_in_for"] = None
                                    p["subbed_in_minute"] = None
                                else:
                                    subbed_out_counts[tgt] = current_cnt + 1
                        logger.info(f"Successfully retrieved and validated match roster for '{team_name}' on attempt {attempt}.")
                        ensure_player_photos(roster, team_name)
                        current_cache = load_cache()
                        current_cache[match_key] = roster
                        save_cache(current_cache)
                        return roster
            except Exception as e:
                logger.error(f"Attempt {attempt} failed to query LLM for match roster of '{team_name}': {e}")
            
            import time
            time.sleep(1.5)

    # 3. Fallback to general roster lookup (predefined list, then cache, then LLM)
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
                raw_content = completion.choices[0].message.content
                if not raw_content:
                    raw_content = getattr(completion.choices[0].message, 'reasoning', None) or ""
                response_text = raw_content.strip()
                
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

    logger.warning(f"Failed to fetch roster for '{team_name}' from LLM/cache. Generating dynamic backend fallback roster...")
    return generate_backend_fallback_roster(team_name, opponent_name)


def is_future_match(date_str: str) -> bool:
    """Checks if a match date is in the future relative to the system time."""
    if not date_str:
        return True
    norm = date_str.lower().strip()
    if "upcoming" in norm or "fixture" in norm:
        return True
    if "today" in norm:
        return True
    import datetime
    now = datetime.datetime.now()
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(norm.title(), fmt)
            if dt.date() > now.date():
                return True
            return False
        except ValueError:
            pass
    return False


def get_dynamic_match_stats_via_llm(
    home: str,
    away: str,
    date: str,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None,
    is_future: bool = False
) -> Dict[str, Any]:
    """
    Dynamically generates or predicts match stats using LLM + Web Search.
    Never hardcodes a specific match's fallback values.
    """
    search_context = ""
    if not is_future:
        try:
            search_query = f"{home} vs {away} {date} match stats possession shots passes"
            results = rag_engine.web_search_fallback(search_query, max_results=3, clean=False)
            if results:
                search_context = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        except Exception as e:
            logger.error(f"Search failed for dynamic stats: {e}")

    prompt = f"""You are a professional football match statistics model.
    Generate a JSON object containing realistic match statistics for:
    Home Team: {home}
    Away Team: {away}
    Date: {date}
    Is Future/Upcoming Match: {is_future}
    Home Team Score (if played): {home_score}
    Away Team Score (if played): {away_score}
    
    """
    if search_context:
        prompt += f"""Here is some search context about the match:\n{search_context}\n
        If the search context contains the actual match statistics, extract and use them. Otherwise, estimate highly realistic statistics that are consistent with the final score of {home_score}-{away_score} and the teams' general tactics and style of play.
        """
    else:
        if is_future:
            prompt += f"""Since this is a future match, predict the match flow and simulate realistic match stats based on the general playing styles and team strength of {home} and {away}.
            """
        else:
            prompt += f"""Estimate highly realistic statistics for this past match that are consistent with the final score of {home_score}-{away_score} and the teams' general tactics and style of play.
            """

    prompt += """
    Your response must be a valid JSON object with the following keys and values:
    - 'possession': An array of two integers representing possession percentage for Home and Away (e.g. [55, 45]). The sum must be exactly 100.
    - 'shots': An array of two integers representing total shots for Home and Away (e.g. [14, 9]).
    - 'bigChances': An array of two integers representing big chances for Home and Away (e.g. [3, 1]).
    - 'passes': An array of two integers representing accurate or total passes for Home and Away (e.g. [510, 420]).
    - 'predicted_score': An array of two integers representing the predicted/actual score (e.g. [2, 1]).
    
    Return ONLY a raw valid JSON object. Do not write any markdown code wrappers, explanations, or notes."""

    if rag_engine.openai_client is not None:
        for attempt in range(1, 4):
            try:
                completion = rag_engine.openai_client.chat.completions.create(
                    model=rag_engine.model_name,
                    messages=[
                        {"role": "system", "content": "You are a database system returning raw JSON objects only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3 + (attempt * 0.1)
                )
                raw_content = completion.choices[0].message.content
                if not raw_content:
                    raw_content = getattr(completion.choices[0].message, 'reasoning', None) or ""
                res_text = raw_content.strip()
                if res_text.startswith("```json"):
                    res_text = res_text[7:]
                if res_text.endswith("```"):
                    res_text = res_text[:-3]
                res_text = res_text.strip()
                
                stats = json.loads(res_text)
                required_keys = {"possession", "shots", "bigChances", "passes"}
                if required_keys.issubset(stats.keys()):
                    # Validate values
                    if isinstance(stats["possession"], list) and len(stats["possession"]) == 2:
                        if sum(stats["possession"]) != 100:
                            stats["possession"] = [50, 50]
                    else:
                        stats["possession"] = [50, 50]
                    
                    for k in ["shots", "bigChances", "passes"]:
                        if not isinstance(stats[k], list) or len(stats[k]) != 2:
                            stats[k] = [0, 0]
                        else:
                            stats[k] = [int(x) for x in stats[k]]
                    
                    if "predicted_score" not in stats or not isinstance(stats["predicted_score"], list) or len(stats["predicted_score"]) != 2:
                        stats["predicted_score"] = [home_score if home_score is not None else 0, away_score if away_score is not None else 0]
                    else:
                        stats["predicted_score"] = [int(x) for x in stats["predicted_score"]]

                    logger.info(f"Successfully generated dynamic stats via LLM: {stats}")
                    return stats
            except Exception as e:
                logger.error(f"Attempt {attempt} failed to generate stats via LLM: {e}")
                import time
                time.sleep(1.0)

    # Procedural fallback
    import random
    seed_val = sum(ord(c) for c in home + away)
    random.seed(seed_val)
    h_poss = random.randint(40, 60)
    a_poss = 100 - h_poss
    h_shots = random.randint(8, 20)
    a_shots = random.randint(6, 18)
    h_bc = max(0, int(h_shots * 0.15))
    a_bc = max(0, int(a_shots * 0.15))
    h_passes = random.randint(350, 600)
    a_passes = random.randint(350, 600)
    return {
        "possession": [h_poss, a_poss],
        "shots": [h_shots, a_shots],
        "bigChances": [h_bc, a_bc],
        "passes": [h_passes, a_passes],
        "predicted_score": [home_score if home_score is not None else 1, away_score if away_score is not None else 1]
    }


def generate_backend_fallback_roster(team_name: str, opponent_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generates a dynamic fallback squad starting XI roster procedurally on the backend."""
    positions = ['GK', 'RB', 'CB', 'CB', 'LB', 'DM', 'CM', 'CM', 'RW', 'ST', 'LW']
    names = {
        'GK': ['Keeper'],
        'RB': ['Right Back'],
        'CB': ['Defender A', 'Defender B'],
        'LB': ['Left Back'],
        'DM': ['Midfielder D'],
        'CM': ['Midfielder A', 'Midfielder B'],
        'RW': ['Winger R'],
        'ST': ['Striker'],
        'LW': ['Winger L']
    }
    
    roster = []
    counts = {}
    for i, pos in enumerate(positions):
        counts[pos] = counts.get(pos, 0) + 1
        name_list = names[pos]
        name = name_list[(counts[pos] - 1) % len(name_list)]
        
        rating = 6.5 + (i % 3) * 0.5
        
        roster.append({
            "name": f"{team_name} {name}",
            "jersey": str(1 if pos == 'GK' else 2 + i),
            "rating": rating,
            "pos": pos,
            "photo": "",
            "age": str(22 + (i % 8)),
            "val": "€15M",
            "height": "182 cm",
            "sofa_id": ""
        })
    return roster


def get_match_stats(
    home: str,
    away: str,
    date: str,
    home_score: Optional[int] = None,
    away_score: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Returns possession, shots, bigChances, and passes for a specific match.
    Checks cache first, then fetches REAL stats from the ESPN public API.
    Falls back to dynamic LLM predicted/estimated stats if ESPN doesn't have it or it's a future match.
    """
    import datetime

    norm_home = normalize_name(home)
    norm_away = normalize_name(away)
    # Resolve "Today" or "Today @ HH:MM" to the real calendar date before normalizing
    resolved_date = date
    if resolved_date.lower().startswith("today"):
        resolved_date = datetime.date.today().strftime("%d %b %Y")
    norm_date = normalize_date_string(resolved_date)

    # Deterministic cache key — sort team names alphabetically so direction doesn't matter
    sorted_teams = sorted([norm_home, norm_away])
    cache_key = f"matchstats_{sorted_teams[0]}_vs_{sorted_teams[1]}_{norm_date}"

    # 1. Cache hit — but for today's matches, skip cached stats so live numbers stay fresh
    is_today_match = norm_date == datetime.date.today().strftime("%d %b %Y").lower()
    cache = load_cache()
    if cache_key in cache and not is_today_match:
        logger.info(f"Match stats for '{home}' vs '{away}' found in cache (key: {cache_key})")
        stats_val = cache[cache_key]
        if stats_val:
            if "predicted_score" not in stats_val:
                stats_val["predicted_score"] = [home_score if home_score is not None else 0, away_score if away_score is not None else 0]
            
            # Extract first team name from the cache key to detect if we need to swap order
            key_without_prefix = cache_key
            if key_without_prefix.startswith("matchstats_"):
                key_without_prefix = key_without_prefix[len("matchstats_"):]
            parts = key_without_prefix.split("_vs_")
            if len(parts) >= 2:
                norm_team1 = normalize_name(parts[0].strip())
                if norm_team1 == norm_away:
                    logger.info(f"Swapping cached stats order to match requested home/away ({home} vs {away})")
                    stats_val = dict(stats_val)
                    for k in ["possession", "shots", "bigChances", "passes", "predicted_score"]:
                        if k in stats_val and isinstance(stats_val[k], list) and len(stats_val[k]) == 2:
                            stats_val[k] = [stats_val[k][1], stats_val[k][0]]
            return stats_val

    is_future = is_future_match(norm_date)


    # 2. Try ESPN soccer scoreboard for past matches
    if not is_future:
        espn_date = None
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
            try:
                espn_date = datetime.datetime.strptime(norm_date.title(), fmt).strftime("%Y%m%d")
                break
            except ValueError:
                pass

        if espn_date:
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }

            # ESPN soccer league slugs — try most likely first
            espn_leagues = [
                "fifa.world", "uefa.champions", "uefa.europa", "eng.1", "esp.1",
                "ger.1", "ita.1", "fra.1", "usa.1", "concacaf.nations.league",
                "conmebol.copa", "afc.asian.cup",
            ]

            def _team_matches(espn_name: str, our_name: str) -> bool:
                a = clean_text(espn_name)
                b = clean_text(our_name)
                return a == b or a in b or b in a or any(w in a for w in b.split() if len(w) > 3)

            event_id = None
            matched_league = None
            home_team_idx = 0  # index of our home team in ESPN's competitors list

            for slug in espn_leagues:
                try:
                    sb_r = requests.get(
                        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={espn_date}",
                        headers=req_headers, timeout=6
                    )
                    if sb_r.status_code != 200:
                        continue
                    for ev in sb_r.json().get("events", []):
                        for comp in ev.get("competitions", []):
                            names = [c.get("team", {}).get("displayName", "") for c in comp.get("competitors", [])]
                            if len(names) < 2:
                                continue
                            if any(_team_matches(n, home) for n in names) and any(_team_matches(n, away) for n in names):
                                event_id = comp.get("id")
                                matched_league = slug
                                home_team_idx = next((i for i, n in enumerate(names) if _team_matches(n, home)), 0)
                                logger.info(f"ESPN event {event_id} found for {home} vs {away} [{slug}]")
                                break
                        if event_id:
                            break
                except Exception as e:
                    logger.debug(f"ESPN scoreboard error [{slug}]: {e}")
                if event_id:
                    break

            if event_id:
                # Fetch real match stats from ESPN summary
                try:
                    sum_r = requests.get(
                        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{matched_league}/summary?event={event_id}",
                        headers=req_headers, timeout=8
                    )
                    if sum_r.status_code == 200:
                        teams_data = sum_r.json().get("boxscore", {}).get("teams", [])
                        if teams_data:
                            def _stat(stat_list, *labels) -> Optional[float]:
                                for s in stat_list:
                                    lbl = s.get("label", "").upper()
                                    for want in labels:
                                        if want.upper() in lbl:
                                            try:
                                                return float(s.get("displayValue", "").replace("%", "").strip())
                                            except ValueError:
                                                pass
                                return None

                            h_stats = teams_data[home_team_idx].get("statistics", []) if len(teams_data) > home_team_idx else []
                            a_stats = teams_data[1 - home_team_idx].get("statistics", []) if len(teams_data) > 1 - home_team_idx else []

                            h_poss   = _stat(h_stats, "Possession")
                            a_poss   = _stat(a_stats, "Possession")
                            h_shots  = _stat(h_stats, "SHOTS", "Shots")
                            a_shots  = _stat(a_stats, "SHOTS", "Shots")
                            h_passes = _stat(h_stats, "Accurate Passes", "Passes")
                            a_passes = _stat(a_stats, "Accurate Passes", "Passes")
                            h_bc     = _stat(h_stats, "ON GOAL")
                            a_bc     = _stat(a_stats, "ON GOAL")

                            if h_poss is not None and h_shots is not None:
                                total_p = (h_poss or 0) + (a_poss or 0)
                                if total_p > 0 and abs(total_p - 100) > 2:
                                    h_poss = round(h_poss / total_p * 100)
                                else:
                                    h_poss = round(h_poss or 50)
                                a_poss = 100 - h_poss

                                stats = {
                                    "possession": [h_poss, a_poss],
                                    "shots":      [int(h_shots or 0),  int(a_shots or 0)],
                                    "bigChances": [int(h_bc or 0),     int(a_bc or 0)],
                                    "passes":     [int(h_passes or 0), int(a_passes or 0)],
                                    "predicted_score": [home_score if home_score is not None else 0, away_score if away_score is not None else 0]
                                }

                                if norm_home == sorted_teams[1]:
                                    cache_stats = {
                                        "possession": [a_poss, h_poss],
                                        "shots":      [int(a_shots or 0),  int(h_shots or 0)],
                                        "bigChances": [int(a_bc or 0),     int(h_bc or 0)],
                                        "passes":     [int(a_passes or 0), int(h_passes or 0)],
                                        "predicted_score": [away_score if away_score is not None else 0, home_score if home_score is not None else 0]
                                    }
                                else:
                                    cache_stats = stats

                                current_cache = load_cache()
                                current_cache[cache_key] = cache_stats
                                save_cache(current_cache)
                                logger.info(f"Cached real ESPN stats for '{home}' vs '{away}': {cache_stats}")
                                return stats
                except Exception as e:
                    logger.error(f"ESPN summary error for event {event_id}: {e}")

    # 3. Dynamic Fallback to LLM / prediction model
    logger.info(f"ESPN lookup missed or match is future ({is_future=}). Generating dynamic stats via LLM...")
    stats = get_dynamic_match_stats_via_llm(home, away, date, home_score, away_score, is_future)
    if stats:
        if norm_home == sorted_teams[1]:
            cache_stats = {
                "possession": [stats["possession"][1], stats["possession"][0]],
                "shots":      [stats["shots"][1], stats["shots"][0]],
                "bigChances": [stats["bigChances"][1], stats["bigChances"][0]],
                "passes":     [stats["passes"][1], stats["passes"][0]],
                "predicted_score": [stats["predicted_score"][1], stats["predicted_score"][0]]
            }
        else:
            cache_stats = stats
        current_cache = load_cache()
        current_cache[cache_key] = cache_stats
        save_cache(current_cache)
        return stats

    return None


# ── Shared ESPN helpers ──────────────────────────────────────────────────────

ESPN_LEAGUES = [
    "fifa.world", "uefa.champions", "uefa.europa",
    "eng.1", "esp.1", "ger.1", "ita.1", "fra.1",
    "usa.1", "concacaf.nations.league", "conmebol.copa", "afc.asian.cup",
]

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def _team_name_matches(espn_name: str, our_name: str) -> bool:
    a = clean_text(espn_name)
    b = clean_text(our_name)
    return a == b or a in b or b in a or any(w in a for w in b.split() if len(w) > 3)


def _resolve_espn_event(home: str, away: str, espn_date: str):
    """
    Searches ESPN scoreboard pages to find the competition event ID for a match.
    Returns (event_id, league_slug, home_team_idx) or (None, None, 0).
    """
    for slug in ESPN_LEAGUES:
        try:
            r = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={espn_date}",
                headers=ESPN_HEADERS, timeout=6
            )
            if r.status_code != 200:
                continue
            for ev in r.json().get("events", []):
                for comp in ev.get("competitions", []):
                    names = [c.get("team", {}).get("displayName", "") for c in comp.get("competitors", [])]
                    if len(names) < 2:
                        continue
                    if any(_team_name_matches(n, home) for n in names) and any(_team_name_matches(n, away) for n in names):
                        event_id = comp.get("id")
                        home_idx = next((i for i, n in enumerate(names) if _team_name_matches(n, home)), 0)
                        logger.info(f"ESPN event {event_id} found for {home} vs {away} [{slug}]")
                        return event_id, slug, home_idx
        except Exception as e:
            logger.debug(f"ESPN scoreboard error [{slug}]: {e}")
    return None, None, 0


def _espn_date_from_norm(norm_date: str) -> Optional[str]:
    import datetime
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(norm_date.title(), fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    return None


# ────────────────────────────────────────────────────────────────────────────


def fetch_real_world_match_events_via_rag(
    home: str,
    away: str,
    date: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Searches the web for match goalscorers and assisters, scrapes the top pages,
    and uses the LLM to extract clean, real-world goal events.
    """
    norm_home = normalize_name(home)
    norm_away = normalize_name(away)
    resolved_date = date
    if resolved_date.lower().startswith("today"):
        import datetime
        resolved_date = datetime.date.today().strftime("%d %b %Y")
    norm_date = normalize_date_string(resolved_date)

    if is_future_match(norm_date):
        logger.info(f"Match '{home}' vs '{away}' is in the future. Returning empty goal events list.")
        return []

    # 1. Search for goals, goalscorers, assists
    search_query = f"{home} vs {away} {resolved_date} goalscorers assists goals score"
    logger.info(f"Triggering live web search for match events: {search_query}")
    search_results = rag_engine.web_search_fallback(search_query, max_results=5, clean=False)

    search_context = ""
    if search_results:
        search_context_parts = []
        for r in search_results:
            search_context_parts.append(f"- {r['title']}: {r['body']}")
        
        # Build keywords list with team name variations
        team_keywords = []
        for team in [home, away]:
            t_norm = normalize_name(team)
            team_keywords.append(t_norm)
            for word in t_norm.split():
                if len(word) > 3:
                    team_keywords.append(word)
        if any(x in team_keywords for x in ["congo dr", "congo"]):
            team_keywords.extend(["congo", "dr congo", "drc"])

        keywords = team_keywords + ["goal", "assist", "score", "minute", "scorer", "penalty", "own goal", "ht", "ft"]

        # Fetch full page text for the top results to avoid hallucinations
        fetched_count = 0
        for r in search_results:
            url = r.get("href", "")
            if url:
                url = _clean_yahoo_url(url)
            if url and not any(loc in url for loc in ["wikipedia.org/wiki/Portugal", "wikipedia.org/wiki/Democratic_Republic_of_the_Congo", "wikipedia.org/wiki/Congo"]):
                try:
                    logger.info(f"Fetching webpage content for events RAG context: {url}")
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                    page_res = requests.get(url, headers=headers, timeout=5.0)
                    if page_res.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(page_res.text, "html.parser")
                        text_content = soup.get_text(separator="\n")
                        
                        # Filter sentences to keep context density high
                        lines = [l.strip() for l in text_content.splitlines() if l.strip()]
                        relevant_sentences = []
                        for line in lines:
                            if any(k in line.lower() for k in keywords) and len(line) < 300:
                                relevant_sentences.append(line)
                        
                        filtered_text = " ".join(relevant_sentences)[:2000]
                        if filtered_text:
                            search_context_parts.append(f"[Webpage Content from {url}]:\n{filtered_text}")
                            fetched_count += 1
                            if fetched_count >= 3:
                                break
                except Exception as fetch_err:
                    logger.warning(f"Failed to fetch webpage content for events: {fetch_err}")

        search_context = "\n\n".join(search_context_parts)

    if not search_context:
        logger.warning(f"No search context found for '{home}' vs '{away}' events.")
        return []

    # 2. LLM Prompt
    prompt = f"""You are a professional football database helper. Your job is to extract the actual, real-world goal events (goalscorers and assists) for the match: '{home}' vs '{away}' played on '{resolved_date}'.

Here is the search context containing match reports, commentaries, or summaries:
{search_context}

Using the search context above, return a JSON list of all actual goals scored during the match.
Each goal event in the list must be a JSON object with exactly the following keys:
- 'minute': the minute of the goal (e.g. "12'" or "45+2'")
- 'scorer': the full name of the goalscorer
- 'assist': the full name of the player who assisted the goal (or null if unassisted)
- 'team': the exact team name who scored (either '{home}' or '{away}')
- 'ownGoal': true if it was an own goal, false otherwise
- 'penalty': true if it was a penalty, false otherwise
- 'text': a short description of the goal

Important Rules:
1. Do NOT make up, predict, or estimate any goals. Extract ONLY the actual goals that occurred as documented in the search context.
2. If the match has not happened yet, or if no goal details are found in the search context, return an empty JSON array [].
3. Ensure the team names match exactly '{home}' or '{away}'.
4. Return ONLY a raw valid JSON array. Do not write any markdown code wrappers, explanations, or notes."""

    if rag_engine.openai_client is not None:
        for attempt in range(1, 4):
            try:
                completion = rag_engine.openai_client.chat.completions.create(
                    model=rag_engine.model_name,
                    messages=[
                        {"role": "system", "content": "You are a database system returning raw JSON arrays only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    timeout=15.0
                )
                raw_content = completion.choices[0].message.content
                if not raw_content:
                    raw_content = getattr(completion.choices[0].message, 'reasoning', None) or ""
                response_text = raw_content.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                goals = json.loads(response_text)
                if isinstance(goals, list):
                    # Validate keys
                    valid = True
                    required_keys = {"minute", "scorer", "assist", "team", "ownGoal", "penalty", "text"}
                    for g in goals:
                        if not required_keys.issubset(g.keys()):
                            valid = False
                            break
                    if valid:
                        # Normalize team name to match exact home/away string
                        for g in goals:
                            g_team = normalize_name(g.get("team", ""))
                            if g_team == normalize_name(home):
                                g["team"] = home
                            elif g_team == normalize_name(away) or g_team in ["dr congo", "drc", "congo dr", "congo"]:
                                g["team"] = away
                        logger.info(f"Successfully retrieved and validated match events for '{home}' vs '{away}' via RAG.")
                        return goals
            except Exception as e:
                logger.error(f"Attempt {attempt} failed to query LLM for match events of '{home}': {e}")
            import time
            time.sleep(1.0)

    return []


def get_match_events(
    home: str,
    away: str,
    date: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns goal events for a match: scorer name, assister name, minute, team, and description.
    Fetches from ESPN keyEvents (scoringPlay=True only). Caches results.
    Returns None if the match is not on ESPN or not yet played.
    """
    norm_home = normalize_name(home)
    norm_away = normalize_name(away)
    # Resolve "Today" or "Today @ HH:MM" to the real calendar date
    resolved_date = date
    if resolved_date.lower().startswith("today"):
        import datetime
        resolved_date = datetime.date.today().strftime("%d %b %Y")
    norm_date = normalize_date_string(resolved_date)

    sorted_teams = sorted([norm_home, norm_away])
    cache_key = f"matchevents_{sorted_teams[0]}_vs_{sorted_teams[1]}_{norm_date}"

    # Cache hit — skip empty-list cache for today (match may be live)
    import datetime as _dt
    is_today = norm_date == _dt.date.today().strftime("%d %b %Y").lower()
    cache = load_cache()
    if cache_key in cache:
        cached_val = cache[cache_key]
        if cached_val or not is_today:
            logger.info(f"Match events for '{home}' vs '{away}' found in cache")
            return cached_val
        logger.info(f"Skipping empty event cache for today's live match '{home}' vs '{away}', re-fetching...")

    espn_date = _espn_date_from_norm(norm_date)
    event_id = None
    matched_league = None
    if espn_date:
        event_id, matched_league, _ = _resolve_espn_event(home, away, espn_date)

        # Midnight-crossing fallback: if match was played yesterday (local clock ticked past midnight),
        # try yesterday's ESPN date before giving up.
        if not event_id and (is_today or date.lower().startswith("today")):
            import datetime as _dt2
            yesterday = (_dt2.date.today() - _dt2.timedelta(days=1)).strftime("%Y%m%d")
            if yesterday != espn_date:
                logger.info(f"Match not found on ESPN for {espn_date}, trying yesterday {yesterday}...")
                event_id, matched_league, _ = _resolve_espn_event(home, away, yesterday)

    if not event_id:
        logger.info(f"ESPN event lookup missed for '{home}' vs '{away}'. Falling back to RAG search for real-world goal events...")
        goals = fetch_real_world_match_events_via_rag(home, away, date)
        if goals is not None:
            current_cache = load_cache()
            current_cache[cache_key] = goals
            save_cache(current_cache)
            logger.info(f"Cached {len(goals)} RAG-extracted goal events for '{home}' vs '{away}'")
            return goals
        return None

    try:
        sum_r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{matched_league}/summary?event={event_id}",
            headers=ESPN_HEADERS, timeout=8
        )
        if sum_r.status_code != 200:
            return None

        raw_events = sum_r.json().get("keyEvents", [])
        goals = []
        for ev in raw_events:
            if not ev.get("scoringPlay"):
                continue

            ev_type = ev.get("type", {}).get("type", "")
            # Include goal, header, penalty-scored, own-goal types
            if "goal" not in ev_type and "penalty" not in ev_type:
                continue

            minute = ev.get("clock", {}).get("displayValue", "?")
            team_name = ev.get("team", {}).get("displayName", "")
            participants = ev.get("participants", [])

            scorer = participants[0]["athlete"]["displayName"] if participants else "Unknown"
            assister = participants[1]["athlete"]["displayName"] if len(participants) > 1 else None

            is_own_goal = "own-goal" in ev_type or "own goal" in ev.get("text", "").lower()
            is_penalty = "penalty" in ev_type

            goals.append({
                "minute": minute,
                "scorer": scorer,
                "assist": assister,
                "team": team_name,
                "ownGoal": is_own_goal,
                "penalty": is_penalty,
                "text": ev.get("shortText", ""),
            })

        # Cache and return
        current_cache = load_cache()
        current_cache[cache_key] = goals
        save_cache(current_cache)
        logger.info(f"Cached {len(goals)} goal events for '{home}' vs '{away}'")
        return goals

    except Exception as e:
        logger.error(f"ESPN events error for event {event_id}: {e}")
        return None
