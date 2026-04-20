content = open('app.py').read()
idx = content.find('drive_get_folder_ids')
if idx > 0:
    print("Trouve a l index:", idx)
    print("Contexte:", content[max(0,idx-100):idx+200])
else:
    print("Non trouve")
