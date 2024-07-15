# visit http://127.0.0.1:8050/ in your web browser
# Import modules
from dash import Dash, html, dcc, dash_table, callback, Output, Input, State
import pandas as pd
import geopandas as gpd
import os
import re


# Automated file list creation
file_path = r'./AADT data/'
file_list = []
for file in os.listdir(file_path):
    if os.path.isfile(os.path.join(file_path, file)):
        file_list.append(file)
        

# Required headers and alternatives (as fail-safe) for the filtered dataframe
preserve_column = ['Loc ID', 'Route', 'BMP', 'Start', 'EMP', 'End', 'K Factor %', 'D Factor %', 'T Factor %', 'AADT_1', 'AADT_2']
alternative_names = {
    'Loc ID': ['LocID', 'Loc_ID', 'LocID_1', 'Location'],
    'Route': ['Road', 'Road1', 'Road_1', 'RouteID', 'Route_ID', 'RouteID_1'],
    'Start': ['FromRoad', 'FromRoad1'],
    'End': ['ToRoad', 'ToRoad1'],
    'AADT_1': [f'AADT {year}' for year in range(2020, 2040)],
    'AADT_2': [f'{year} Future AADT' for year in range(2040, 2070)]}
present_year_dash = 1
future_year_dash = 2

# Core keywords to scan the correct header row
keywords = ['BMP','EMP']    # BMP and EMP are the most consistent keywords


# Function to dynamically select the header in the excel file
def find_header_row(file, keywords, df_no_header):
    # Iterate through each row and find matching keywords
    for index, row in df_no_header.iterrows():
        if any(keywords.lower() in str(row).lower() for keywords in keywords):
            # Return the index of the row
            return index
    # If no keywords present, return None
    return None


# Function to check for AADT validity, save to CSV file
def validity_check(present_year, future_year, df):
    issue_path = r'./AADT issues/'
    file_name = 'AADT ' + str(present_year) + ' issues.csv'
    existing_issue = os.path.join(issue_path, file_name)
    # Create a new validity column
    all_years = [present_year, future_year]
    all_years.sort()
    # Create a new dataframe to store the checked data
    # Validity checking is based on whether the present AADT is less than the future AADT
    df_issue = df
    df_issue['Validity'] = df.apply(lambda row: 'Good' if 
                                    (row[f'AADT {all_years[0]}'] <= row[f'AADT {all_years[1]}']) 
                                    else 'Bad', axis=1)
    # Check if there are invalid data rows to determine the existence of invalid data
    # If invalid data exists, determine the existence of any file with same name
    if (df_issue['Validity'] == 'Bad').any():
        # Check for files with the same name
        if file_name in os.listdir(existing_issue):
            df_existing = pd.read_csv(existing_issue)
            # Overwrite the existing CSV file, if the contents are not the same, otherwise ignore
            if not df_existing.equals(df_issue):
                df_issue.to_csv(existing_issue, index = False)
        # Save to CSV file, if there file with the same name does not exist
        else:
            df_issue.to_csv(existing_issue, index = False)
    # If no invalid data exists, remove any file with the same name, otherwise ignore
    else:
        # Check for files with the same name
        if file_name in os.listdir(existing_issue):
            os.remove(existing_issue)
        
    
# Function to filter the AADT data
def filtered_AADT(file):
    global present_year
    # Clear the dataframes before reuse
    df = pd.DataFrame()
    df_no_header = pd.DataFrame()
    df_original = pd.DataFrame()
    
    # Read the selected excel file without the header
    df_no_header = pd.read_excel(file, header = None)
    # Read the selected excel file with the derived header
    df_original = pd.read_excel(file, header = find_header_row(file, keywords, df_no_header))  
    
    # Iterate over each required information, check if it exists or use alternative name
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
                        df.rename(columns={'AADT_1': f'AADT {present_year}'}, inplace=True)
                        # Create a copy of the column for future use
                        df[col] = df_original[alt_name]
                    elif col == 'AADT_2':
                        future_year = re.search(r'\d+', alt_name).group()
                        df.rename(columns={'AADT_1': f'AADT {future_year}'}, inplace=True)
                        # Create a copy of the column for future use
                        df[col] = df_original[alt_name]
                    # End the loop if an alternate name is found
                    break
                
    # Filter out data with no BMP values and store to new dataframe
    df = df[df['BMP'].notna() & (df['BMP'] != '-')]
 
    # Return the filtered dataframe
    return df
   
    
# Create a dictionary, for forecasting and dropdown selection 
filtered_file = {}

# Iterate through the file list, save the filtered data and create their list
for file in file_list:
    filtered_path = os.path.join(file_path, file)
    # Clear the dataframe before reuse
    df_filtered = pd.DataFrame()
    # Save the filtered dataframe
    df_filtered = filtered_AADT(file)
    df_filtered.to_csv(file, index = False)

    # Append to the dropdown list after creating a new name
    file_dropdown = 'AADT-' + present_year + ' table'
    filtered_file[file] = file_dropdown
    

# Start of dash app
app = Dash(__name__)


# Dash app layout
app.layout = html.Div([
    # Silently store the year variables within dash
    dcc.Input(id = 'present-year-dash', type = 'hidden', value = present_year_dash),
    dcc.Input(id = 'future-year-dash', type = 'hidden', value = future_year_dash),
    # File dropdown selection
    dcc.Dropdown(
        options = [{'label': file, 'value': file} for file in filtered_file.keys()],
        value = next(iter(filtered_file.keys())),
        id = 'file-dropdown',
    ),
    # Route dropdown selection
    dcc.Dropdown(
        placeholder = 'Please select a file first...',
        id = 'route-dropdown'
    ),
    # BMP input box
    html.Label('BMP'),
    dcc.Input(
        value = 0,
        type = 'number',
        id = 'BMP-id'
    ),   
    # EMP input box
    html.Label('EMP'),
    dcc.Input(
        value = 1000,
        type = 'number',
        id = 'EMP-id'
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
        id = 'dash-table',
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
    Output('file-dropdown', 'value'),
    [Input('file-dropdown', 'value')]
)

# Function to return the selected file
def file_dropdown(selected_dropdown):
    # Inverse lookup to find the file name based on the dropdown name
    for selected_file, dropdown_name in filtered_file.items():
        if dropdown_name == selected_dropdown:
            return selected_file
    

# Callback decorator for route selection after file selection
@callback(
    [Output('route-dropdown', 'options'),
     Output('present-year-dash', 'value'),
     Output('future-year-dash', 'value')],
    [Input('file-dropdown', 'value')]   
)

# Function to dynamically update the route selection based on the current selected file
def update_routes(selected_file):
    global df_dash
    global present_year_dash
    global future_year_dash
    # Initialize the years to 0
    present_year_dash = 0
    future_year_dash = 0
    
    # Clear the dataframe before reuse
    df_dash = pd.DataFrame()
    df_dash = pd.read_csv(selected_file)
    
    # Iterate over column, check for the substrings, store the years and rename their columns
    for col in df_dash.columns:
        if 'AADT_1' in col:
            present_year_dash = col.split(' ')[-1]
            df_dash.rename(columns={col: 'AADT {present_year_dash}'})
        elif 'AADT_2' in col:
            future_year_dash = col.split(' ')[-1]
            df_dash.rename(columns={col: 'AADT {future_year_dash}'})
        # Break the column if both the years are not zero
        elif present_year_dash != 0 and future_year_dash != 0:
            break
    
    # Convert to integer for forecasting
    present_year_dash = int(present_year_dash)
    future_year_dash = int(future_year_dash)
    
    # Get the unique routes from the selected file
    options = [{'label': route, 'value': route} for route in df_dash['Route'].unique()]
    return options, present_year_dash, future_year_dash


# Callback decorator for BMP limiter
@app.callback(
    Output('BMP-id', 'value'),
    [Input('BMP-id', 'value')]
)

# Returns 0 if value is less than 0
def update_bmp_value(BMP):
    if BMP < 0:
        return 0
    else:
        return BMP
   
   
# Callback decorator for EMP limiter
@app.callback(
    Output('EMP-id', 'value'),
    [Input('EMP-id', 'value')]
)

# Returns 0 if value is less than 0
def update_emp_value(EMP):
    if EMP < 0:
        return 0
    else:
        return EMP

  
# Callback decorator for table display and update
@callback(
    Output('dash-table', 'data'),
    [Input('route-dropdown', 'value'),
     Input('BMP-id', 'value'),
     Input('EMP-id', 'value'),
     Input('year-1', 'value'),
     Input('year-2', 'value'),
     Input('present-year-dash', 'value'),
     Input('future-year-dash', 'value')]
)

# Displays the table and updates according to user input
def update_table(Route, BMP_value, EMP_value, Year_1, Year_2, present_year_dash, future_year_dash):
    # Show all routes if none selected
    if Route is None: 
        df2 = df_dash
    else:
        df2 = df_dash[df_dash['Route'].isin([Route])]
    
    # Keep the entries within the specified range
    df3 = df2[(df2['BMP'] < EMP_value) & (df2['EMP'] > BMP_value)]
    df4 = df3
    
    # AADT formulae
    if Year_1 <= future_year_dash:
        df4[f'AADT {Year_1}'] = df3[f'AADT {present_year_dash}']*((1+(((df3[f'AADT {future_year_dash}']/df3[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_1 - present_year_dash))
    else:
        df4[f'AADT {Year_1}'] = df3[f'AADT {future_year_dash}']*((1+(((df3[f'AADT {future_year_dash}']/df3[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_1 - future_year_dash))
    if Year_2 <= future_year_dash:
        df4[f'AADT {Year_2}'] = df3[f'AADT {present_year_dash}']*((1+(((df3[f'AADT {future_year_dash}']/df3[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_2 - present_year_dash))
    else:
        df4[f'AADT {Year_2}'] = df3[f'AADT {future_year_dash}']*((1+(((df3[f'AADT {future_year_dash}']/df3[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_2 - future_year_dash))
    df4[f'AADT {Year_1}'] = df4[f'AADT {Year_1}'].astype(int)
    df4[f'AADT {Year_2}'] = df4[f'AADT {Year_2}'].astype(int)
    
    # List and sort all the years and add commas to AADT values
    all_years = [present_year_dash, future_year_dash, Year_1, Year_2]
    for year in all_years:
        df4[f'AADT {year}'] = df4[f'AADT {year}'].apply(lambda x: '{:,.0f}'.format(x) if pd.notnull(x) else '')

    return df4.to_dict('records')


# Callback decorator for download function
@callback(
    Output('export-csv', 'data'),
    [Input('export-csv-button', 'n_clicks'),
     Input('present-year-dash', 'value')],
    [State('dash-table', 'data'),
     State('route-dropdown', 'value'),
     State('BMP-id', 'value'),
     State('EMP-id', 'value'),
     State('year-1', 'value'),
     State('year-2', 'value')]
)

# Downloads the table in CSV file format
def export_to_csv(n_clicks, present_year_dash, table_data, Route, BMP_value, EMP_value, Year_1, Year_2):
    # n_clicks prevents the unnecessary download as soon as the website opens
    if n_clicks > 0:
        df_export = pd.DataFrame.from_dict(table_data)
        
        # File name is based on selection route, BMP and EMP
        if Route is None:
            file_name = 'AADT-'+str(present_year_dash)+'-Table All-Routes BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
        else:
            file_name = 'AADT-'+str(present_year_dash)+'-Table '+str(Route)+' BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
            
        return dcc.send_data_frame(df_export.to_csv, file_name, index=False, encoding='utf-8-sig')
    
    
# End of dash app
if __name__ == '__main__':
    app.run(debug = True)