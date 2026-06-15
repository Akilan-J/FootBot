def simulate_static():
    W = 800
    H = 720
    startY = H * 0.1
    teamH = H * 0.38
    isHome = True
    
    # Germany roles
    roles = ['GK', 'RDM', 'RCB', 'LCB', 'LB', 'LCM', 'RCM', 'CAM', 'RW', 'LW', 'ST']
    names = ['Neuer', 'Kimmich', 'Süle', 'Rüdiger', 'Raum', 'Goretzka', 'Gündogan', 'Müller', 'Gnabry', 'Sané', 'Havertz']
    
    # Curaçao roles
    roles_cur = ['GK', 'RB', 'LCB', 'RCB', 'LB', 'CM', 'CM', 'CAM', 'RW', 'ST', 'LW']
    names_cur = ['de Boer', 'Zonneveld', 'Owusu-Abeyie', 'Wau', 'Koren', 'Gaari', 'Hanssen', 'J. Bacuna', 'L. Bacuna', 'van Kessel', 'Elkinson']

    def layout(roles, names, is_home):
        # 1. Normalize roles
        normalized = []
        for i, r in enumerate(roles):
            role = r.upper()
            if role == 'CDM': role = 'DM'
            if role == 'AM': role = 'CAM'
            if role in ['CF', 'FW']: role = 'ST'
            normalized.append((role, names[i]))
            
        # 2. Count occurrences of each role
        roleCounts = {}
        for role, _ in normalized:
            roleCounts[role] = roleCounts.get(role, 0) + 1
            
        roleIndices = {}
        positions = []
        
        for role, name in normalized:
            occurrence = roleIndices.get(role, 0)
            roleIndices[role] = occurrence + 1
            count = roleCounts[role]
            
            x, y = 50, 50
            
            # GK
            if role == 'GK':
                x, y = 50, 4
            # Fullbacks
            elif role in ['LB', 'LWB']:
                x, y = 15, 20
            elif role in ['RB', 'RWB']:
                x, y = 85, 20
            # Center Backs
            elif role == 'CB':
                if count == 1:
                    x, y = 50, 18
                elif count == 2:
                    x, y = (34, 18) if occurrence == 0 else (66, 18)
                else:
                    x, y = (30, 18) if occurrence == 0 else (50, 18) if occurrence == 1 else (70, 18)
            elif role == 'LCB':
                x, y = 34, 18
            elif role == 'RCB':
                x, y = 66, 18
            # Defensive Midfield
            elif role == 'LDM':
                x, y = 32, 38
            elif role == 'RDM':
                x, y = 68, 38
            elif role == 'DM':
                if count == 1:
                    x, y = 46, 38
                else:
                    x, y = (32, 38) if occurrence == 0 else (68, 38)
            # Central Midfield
            elif role == 'LCM':
                x, y = 26, 55
            elif role == 'RCM':
                x, y = 74, 55
            elif role == 'CM':
                if count == 1:
                    x, y = 54, 55
                elif count == 2:
                    x, y = (26, 55) if occurrence == 0 else (74, 55)
                else:
                    x, y = (26, 55) if occurrence == 0 else (54, 55) if occurrence == 1 else (74, 55)
            elif role == 'LM':
                x, y = 14, 55
            elif role == 'RM':
                x, y = 86, 55
            # Attacking Midfield
            elif role == 'LAM':
                x, y = 28, 72
            elif role == 'RAM':
                x, y = 72, 72
            elif role == 'CAM':
                if count == 1:
                    x, y = 46, 72
                else:
                    x, y = (32, 72) if occurrence == 0 else (68, 72)
            elif role == 'SS':
                x, y = 54, 72
            # Forwards / Wingers
            elif role == 'LW':
                x, y = 15, 83
            elif role == 'RW':
                x, y = 85, 83
            elif role == 'LST':
                x, y = 35, 89
            elif role == 'RST':
                x, y = 65, 89
            elif role == 'ST':
                if count == 1:
                    x, y = 50, 89
                else:
                    x, y = (35, 89) if occurrence == 0 else (65, 89)
                    
            xPx = 28 + (x / 100) * (W - 56)
            yPx = startY + (y / 100) * teamH if is_home else startY + (1 - (y / 100)) * teamH
            positions.append({ 'x': xPx, 'y': yPx, 'name': name, 'role': r })
            
        return positions

    print("Germany (Home):")
    for p in layout(roles, names, True):
        print(f"{p['name']} ({p['role']}): x={p['x']:.2f}, y={p['y']:.2f}")
        
    print("\nCuraçao (Away):")
    for p in layout(roles_cur, names_cur, False):
        print(f"{p['name']} ({p['role']}): x={p['x']:.2f}, y={p['y']:.2f}")

if __name__ == '__main__':
    simulate_static()
