# visit http://127.0.0.1:8050/ in your web browser
# Import modules
from dash import Dash, html, dcc, dash_table, callback, Output, Input, State
import pandas as pd
import geopandas as gpd
import os
import re


# Core keywords to scan the correct header row
keywords = ['BMP','EMP']    # BMP and EMP are the most consistent keywords


# Directory of the shapefile
shapefile_path = r'./Shapefile/AADTPublication.shp'
gdf = gpd.read_file(shapefile_path)
gdf = gdf[gdf['BMP'].notna() & (gdf['BMP'] != '-')]


# Automated file list creation
file_path = r'./AADT data/'
file_list = []
for file in os.listdir(file_path):
    if os.path.isfile(os.path.join(file_path, file)):
        file_list.append(file)
        
        
# Function to dynamically select the header in the excel file
def find_header_row(file_loc, keywords):
    df_original = pd.read_excel(file_loc, header = None)
    
    # Iterate through each row and find matching keywords
    for index, row in df_original.iterrows():
        if any(keywords.lower() in str(row).lower() for keywords in keywords):
            # Return the index of the row
            return index
        
    # If no keywords present, return None
    return None


# Preserve only the required information into a new dataframe and provide alternative names as a fail-safe
preserve_column = ['Loc ID', 'Route', 'BMP', 'Start', 'EMP', 'End', 'K Factor %', 'D Factor %', 'T Factor %', 'AADT_1', 'AADT_2']
alternative_names = {
    'Loc ID': ['LocID', 'Loc_ID', 'LocID_1', 'Location'],
    'Route': ['Road', 'Road1', 'Road_1', 'RouteID', 'Route_ID', 'RouteID_1'],
    'Start': ['FromRoad', 'FromRoad1'],
    'End': ['ToRoad', 'ToRoad1'],
    'AADT_1': [f'AADT {year}' for year in range(2020, 2040)],
    'AADT_2': [f'{year} Future AADT' for year in range(2040, 2060)]}


# Create a new dataframe
df = pd.DataFrame()


# Function to iterate over each required information, check if it exists or use alternative name
def preserve_info(preserve_column, df_original, df):
    global present_year
    global future_year
    for col in preserve_column:
        # Use original name if it exists
        if col in df_original.columns:
            df[col] = df_original[col]
        # Iterate over each alternative name
        else:
            for alt_name in alternative_names.get(col, []):
                # Use alternative name if it exists
                if alt_name in df_original:
                    df[col] = df_original[alt_name]
                    # Store only the year from the alternative names for each AADT column to rename and forecast
                    if col == 'AADT_1':
                        present_year = re.search(r'\d+', alt_name).group()
                    elif col == 'AADT_2':
                        future_year = re.search(r'\d+', alt_name).group()
                    # End the loop if an alternate name is found
                    break

    # Rename the columns
    df.rename(columns={'AADT_1': f'AADT {present_year}', 'AADT_2': f'AADT {future_year}'}, inplace=True)
    
    # Filter out data with no BMP values 
    df = df[df['BMP'].notna() & (df['BMP'] != '-')]
     
    # Convert to integer for forecasting
    present_year = int(present_year)
    future_year = int(future_year)


# Start of dash app
app = Dash(__name__)


# Dash app layout
app.layout = html.Div([
    # Silently store the year variables within dash
    # dcc.Input(id='present_year', type='hidden', value=present_year),
    # dcc.Input(id='future_year', type='hidden', value=future_year),
    # File dropdown selection
    dcc.Dropdown(
        options = [{'label': file, 'value': file} for file in file_list],
        value = file_list[0],
        id = 'file-dropdown'
    ),
    # Route dropdown selection
    dcc.Dropdown(
        options = [{'label':route, 'value':route} for route in df['Route'].unique()],
        id = 'route'
    ),
    # BMP input box
    html.Label('BMP'),
    dcc.Input(
        value = 0,
        type = 'number',
        id = 'BMP'
    ),   
    # EMP input box
    html.Label('EMP'),
    dcc.Input(
        value = 1000,
        type = 'number',
        id = 'EMP'
    ),  
    # Year input box
    html.Label('Construction Year'),
    dcc.Input(
        value = 2025,
        type = 'number',
        id = 'year-1'
    ),
    # Year input box
    html.Label('Future Year'),
    dcc.Input(
        value = 2050,
        type = 'number',
        id = 'year-2'
    ),
    # Table display function
    dash_table.DataTable(
        id = 'table',
        page_size = 15  # Affects the number of entries per page
    ),
    # Export to CSV button
    html.Button(
        'Export to CSV',
        id='export-csv-button',
        n_clicks=0      # Records the number of button clicks, required to prevent unnecessary download upon loading the page
    ), 
    # Download function
    dcc.Download(id="export-csv"),
])


# Callback decorator for file selection
@app.callback(
    Output('output-file', 'children'),
    [Input('file-dropdown', 'value')]
)

# Function to dynamically select the header in the excel file
def update_header_row(selected_file):
    global df_original
    if selected_file:
        header_row = find_header_row(os.path.join(file_path, selected_file), keywords)
        # Read the excel file based on the directory and header
        df_original = pd.read_excel(os.path.join(file_path, selected_file), header = header_row)
        preserve_info(preserve_column, df_original, df)
    else:
        return ""
    
    
# Callback decorator for BMP limiter
@app.callback(
    Output('BMP', 'value'),
    [Input('BMP', 'value')]
)

# Returns 0 if value is less than 0
def update_bmp_value(BMP):
    if BMP < 0:
        return 0
    else:
        return BMP
   
   
# Callback decorator for EMP limiter
@app.callback(
    Output('EMP', 'value'),
    [Input('EMP', 'value'),]
)

# Returns 0 if value is less than 0
def update_emp_value(EMP):
    if EMP < 0:
        return 0
    else:
        return EMP

  
# Callback decorator for table display and update
@callback(
    Output('table', 'data'),
    [Input('route', 'value'),
    Input('BMP', 'value'),
    Input('EMP', 'value'),
    Input('year-1', 'value'),
    Input('year-2', 'value')]
)

# Displays the table and updates according to user input
def update_table(Route, BMP_value, EMP_value, Year_1, Year_2):
    # Show all routes if none selected
    if Route is None: 
        df2 = df
    else:
        df2 = df[df['Route'].isin([Route])]
    
    # Keep the entries within the specified range
    df3 = df2[(df2['BMP'] < EMP_value) & (df2['EMP'] > BMP_value)]
    df4 = df3
    
    # AADT formulae
    if Year_1 <= future_year:
        df4[f'AADT {Year_1}'] = df3[f'AADT {present_year}']*((1+(((df3[f'AADT {future_year}']/df3[f'AADT {present_year}'])**(1/(future_year-present_year)))-1))**(Year_1 - present_year))
    else:
        df4[f'AADT {Year_1}'] = df3[f'AADT {future_year}']*((1+(((df3[f'AADT {future_year}']/df3[f'AADT {present_year}'])**(1/(future_year-present_year)))-1))**(Year_1 - future_year))
    if Year_2 <= future_year:
        df4[f'AADT {Year_2}'] = df3[f'AADT {present_year}']*((1+(((df3[f'AADT {future_year}']/df3[f'AADT {present_year}'])**(1/(future_year-present_year)))-1))**(Year_2 - present_year))
    else:
        df4[f'AADT {Year_2}'] = df3[f'AADT {future_year}']*((1+(((df3[f'AADT {future_year}']/df3[f'AADT {present_year}'])**(1/(future_year-present_year)))-1))**(Year_2 - future_year))
    df4[f'AADT {Year_1}'] = df4[f'AADT {Year_1}'].astype(int)
    df4[f'AADT {Year_2}'] = df4[f'AADT {Year_2}'].astype(int)
    
    # List and sort all the years
    all_years = [present_year, future_year, Year_1, Year_2]
    all_years.sort()
    
    # Create a new column to specify the data validity
    # If AADT values are in ascending order, then data is good
    df4['Data Validity'] = df4.apply(lambda row: 'Good' if 
                                   (row[f'AADT {all_years[0]}'] <= row[f'AADT {all_years[1]}'] <= 
                                    row[f'AADT {all_years[2]}'] <= row[f'AADT {all_years[3]}']) 
                                   else 'Bad', axis=1)
    
    # Add commas to AADT values
    for year in all_years:
        df4[f'AADT {year}'] = df4[f'AADT {year}'].apply(lambda x: '{:,.0f}'.format(x) if pd.notnull(x) else '')

    return df4.to_dict('records')


# Callback decorator for download function
@callback(
    Output('export-csv', 'data'),
    [Input('export-csv-button', 'n_clicks')],
    [State('table', 'data'),
     State('route', 'value'),
     State('BMP', 'value'),
     State('EMP', 'value'),
     State('year-1', 'value'),
     State('year-2', 'value')]
)

# Downloads the table in CSV file format
def export_to_csv(n_clicks, table_data, Route, BMP_value, EMP_value, Year_1, Year_2):
    # n_clicks prevents the unnecessary download as soon as the website opens
    if n_clicks > 0:
        df_export = pd.DataFrame.from_dict(table_data)
        
        # File name is based on selection route, BMP and EMP
        if Route is None:
            file_name = 'All-Routes BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
        else:
            file_name = str(Route)+' BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
            
        return dcc.send_data_frame(df_export.to_csv, file_name, index=False, encoding='utf-8-sig')


# End of dash app
if __name__ == '__main__':
    app.run(debug = True)