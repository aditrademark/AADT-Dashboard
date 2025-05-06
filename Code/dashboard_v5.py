# visit http://127.0.0.1:8050/ in your web browser
# Import modules
from dash import Dash, html, dcc, dash_table, callback, Output, Input, State
import pandas as pd
import os
import re


# Automated file list creation
file_path = r'./AADT data/'
filtered_path = r'./AADT filtered data/'
file_list = []
dropdown_list = []
for files in os.listdir(file_path):
    if os.path.isfile(os.path.join(file_path, files)):
        file_list.append(os.path.join(file_path, files))
        
# Core keywords to scan the correct header row
keywords = ['BMP','EMP']    # BMP and EMP are the most consistent keywords

# Required headers and alternatives (as fail-safe) for the filtered dataframe
preserve_column = ['Loc ID', 'Route', 'BMP', 'Start', 'EMP', 'End', 'K Factor %', 'D Factor %', 'T Factor %', 'AADT_1', 'AADT_2']
alternative_names = {
    'Loc ID': ['LocID', 'Loc_ID', 'LocID_1', 'Location'],
    'Route': ['Road', 'Road1', 'Road_1', 'RouteID', 'Route_ID', 'RouteID_1'],
    'Start': ['FromRoad', 'FromRoad1'],
    'End': ['ToRoad', 'ToRoad1'],
    'AADT_1': [f'AADT {year}' for year in range(2020, 2040)],
    'AADT_2': [f'{year} Future AADT' for year in range(2040, 2070)]}


# Function to dynamically select the header in the excel file
def find_header_row(file, df_no_header):
    # Iterate through each row and find matching keywords
    for index, row in df_no_header.iterrows():
        if any(keywords.lower() in str(row).lower() for keywords in keywords):
            # Return the index of the row
            return index
    # If no keywords present, return None
    return None

  
# Function to check for AADT validity, save the valid datasets and create a dropdown list for dash
def validity_check(present_year, future_year, df):
    global flag
    
    # Directory for AADT issues
    issue_path = r'./AADT issues/'
    file_name = 'AADT ' + str(present_year) + ' issues.csv'
    filtered_name = 'AADT ' +str(present_year) + ' Table.csv'
    existing_issue = os.path.join(issue_path, file_name)
    
    # Create a new dataframe to store the checked data
    # Validity checking is based on whether the present AADT is less than the future AADT
    df_issue = df
    df_issue['Validity'] = df_issue.apply(lambda row: 'Good' if 
                                    (row[f'AADT {present_year}'] <= row[f'AADT {future_year}']) 
                                    else 'Bad', axis=1)
    # Filter out the valid data
    df_issue = df_issue[df_issue['Validity'] == 'Bad']
    
    # Check if there are invalid data rows to determine the existence of invalid data
    # If invalid data exists, determine the existence of any file with same name
    if (df_issue['Validity'] == 'Bad').any():
        flag = 1
        print('Warning: Invalid data detected, filtered data not saved')
        # Check for files with the same name
        if os.path.exists(existing_issue):
            df_existing = pd.read_csv(existing_issue)
            # Overwrite the existing CSV file, if the contents are not the same, otherwise ignore
            if not df_existing.equals(df_issue):
                print('Action: Replacing the old log file\n')
                df_issue.to_csv(existing_issue, index = False)
        # Save to CSV file, if there file with the same name does not exist
        else:
            print('Action: Generating log file\n')
            df_issue.to_csv(existing_issue, index = False)
            
    # If no invalid data exists, remove any file with the same name, otherwise ignore
    else:
        flag = 0
        df.drop(columns=['Validity', f'AADT {present_year}', f'AADT {future_year}'], inplace=True)
        df.to_csv(os.path.join(filtered_path, filtered_name), index = False)
        print('Action: Filtered data saved\n')
        if os.path.exists(existing_issue):
            os.remove(existing_issue)
        
    # Return the filtered name for the dropdown list 
    return filtered_name
            
            
# Function to filter the AADT data
def AADT_filter(file):
    global present_year
    global future_year
    global dropdown_list
    
    # Clear the dataframes before reuse
    df = pd.DataFrame()
    df_no_header = pd.DataFrame()
    df_original = pd.DataFrame()
    temp = file.split('/')[-1]
    print(f'Reading {temp}...')
    
    # Create a list to display the missing headers
    missing_headers = []
    flag_missing_header = False
    
    # Read the selected excel file without the header
    df_no_header = pd.read_excel(file, header = None)
    # Read the selected excel file with the derived header
    df_original = pd.read_excel(file, header =find_header_row(file, df_no_header))  
    
    # Iterate over each required information, check if it exists or use alternative name
    for col in preserve_column:
        # Use original name if it exists
        if col in df_original.columns:
            df[col] = df_original[col]
        # Iterate over each alternative name
        else: 
            flag_missing_header = False
            for alt_name in alternative_names.get(col, []):
                # Use alternative name if it exists
                if alt_name in df_original:
                    df[col] = df_original[alt_name]
                    # Store only the year from the alternative names for each AADT column for validation
                    if col == 'AADT_1':
                        # Rename the column to a convenient name for future forecasting
                        present_year = re.search(r'\d+', alt_name).group()
                        df['AADT_1_copy'] = df[col].copy()
                        df.rename(columns={'AADT_1': f'AADT_1-AADT {present_year}'}, inplace=True) 
                        df.rename(columns={'AADT_1_copy': f'AADT {present_year}'}, inplace=True)    
                    elif col == 'AADT_2':
                        # Rename the column to a convenient name for future forecasting
                        future_year = re.search(r'\d+', alt_name).group()
                        df['AADT_2_copy'] = df[col].copy()
                        df.rename(columns={'AADT_2': f'AADT_2-AADT {future_year}'}, inplace=True) 
                        df.rename(columns={'AADT_2_copy': f'AADT {future_year}'}, inplace=True)   
                    flag_missing_header = True
                    # End the loop if an alternate name is found
                    break
                             
            if not flag_missing_header:
                missing_headers.append(col)
    
    # Skip the file, if any headers are missing
    if missing_headers:
        print(f'Error: Column header with a matching name for {missing_headers} was not found')
        print(f'Action: Skipping {temp}\n')
        return 0
                                                         
    # Filter out data with no BMP values and store to new dataframe
    df = df[df['BMP'].notna() & (df['BMP'] != '-')]
    print('Message: Data filteration complete')
    
    # Apply data validation function to the dataframe
    dropdown = (validity_check(present_year, future_year, df)).split('.')[0]
    # Append to the dropdown list, if data is valid
    if flag == 0:
        dropdown_list.append(dropdown)


# Iterate through the file list, save the filtered data and sort their names in a list
for file in file_list:
    AADT_filter(file)
dropdown_list.sort()

# Check if the dropdown list is empty
# Set the default to None, if empty
if not dropdown_list:
    dropdown_placeholder = 'No available datasets'
    dropdown_default = None
    print('Warning: There are no available datasets')
# Set the default to the last dataset, if not empty
else:
    dropdown_placeholder = 'Select a dataset...'
    dropdown_default = dropdown_list[-1]
    print(f'Available datasets: {dropdown_list}\n')


# Start of dash app
app = Dash(__name__)


# Dash app layout
app.layout = html.Div([
    # Silently store the year variables within dash
    dcc.Input(id = 'present-year-dash', type = 'hidden', value = 1),
    dcc.Input(id = 'future-year-dash', type = 'hidden', value = 2),
    # File dropdown selection
    dcc.Dropdown(
        options = [{'label': option, 'value': option} for option in dropdown_list],
        value = dropdown_default,
        placeholder = dropdown_placeholder,
        id = 'file-dropdown',
    ),
    # Route dropdown selection
    dcc.Dropdown(
        placeholder = 'Please select a route...',
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
        value = 2030,
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


# Callback decorator for route selection after file selection
@callback(
    [Output('route-dropdown', 'options'),
     Output('present-year-dash', 'value'),
     Output('future-year-dash', 'value'),
     Output('export-csv-button', 'n_clicks')],
    [Input('file-dropdown', 'value')]   
)

# Function to dynamically update the route selection based on the current selected file
def update_routes(selected_file):
    global df_dash
    
    # Initialize the years to 0
    present_year_dash = 0
    future_year_dash = 0
    
    # Reset the number of export button clicks to zero to prevent downloads when this callback is triggered
    n_clicks = 0
    
    # Clear the dataframe before reuse
    df_dash = pd.DataFrame()
    df_dash = pd.read_csv(filtered_path+selected_file+'.csv')
    
    # Pattern to find the AADT columns
    pattern_1 = r'AADT_1-AADT\s+(\d+)'
    pattern_2 = r'AADT_2-AADT\s+(\d+)'
    
    # Iterate over column, check for the substrings, store the years and rename their columns
    for col in df_dash.columns:
        if re.match(pattern_1, col):
            present_year_dash = col.split(' ')[-1]
            df_dash.rename(columns={col: f'AADT {present_year_dash}'}, inplace=True)
        elif re.match(pattern_2, col):
            future_year_dash = col.split(' ')[-1]
            df_dash.rename(columns={col: f'AADT {future_year_dash}'}, inplace=True)
        # Break the column if both the years are not zero
        elif present_year_dash != 0 and future_year_dash != 0:
            break
    
    # Convert to integer for forecasting
    present_year_dash = int(present_year_dash)
    future_year_dash = int(future_year_dash)
    
    # Get the unique routes from the selected file
    route_options = [{'label': route, 'value': route} for route in df_dash['Route'].unique()]
    return route_options, present_year_dash, future_year_dash, n_clicks
    

# Callback decorator for BMP limiter
@app.callback(
    Output('BMP-id', 'value'),
    [Input('BMP-id', 'value')]
)

# Returns 0 if value is less than 0 or strings
def update_bmp_value(BMP):
    if BMP < 0:
        return 0
    elif isinstance(BMP, str) and any(c in '-+' for c in BMP):
        return 0
    else:
        return BMP
   
   
# Callback decorator for EMP limiter
@app.callback(
    Output('EMP-id', 'value'),
    [Input('EMP-id', 'value')]
)

# Returns 0 if value is less than 0 or strings
def update_emp_value(EMP):
    if EMP < 0:
        return 0
    elif isinstance(EMP, str) and any(c in '-+' for c in EMP):
        return 0
    else:
        return EMP
    

# Callback decorator for construction year limiter
@app.callback(
    Output('year-1', 'value'),
    [Input('year-1', 'value')]
)

# Returns maximum limit 2050 if value is greater than 2050
def update_year_1(Year_1):
    if Year_1 > 2050:
        return 2050
    else:
        return Year_1


# Callback decorator for future year limiter
@app.callback(
    Output('year-2', 'value'),
    [Input('year-2', 'value')]
)

# Returns maximum limit 2050 if value is greater than 2050
def update_year_2(Year_2):
    if Year_2 > 2050:
        return 2050
    else:
        return Year_2
    
    
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
    df2 = df2[(df2['BMP'] < EMP_value) & (df2['EMP'] > BMP_value)]
    
    # AADT formulae
    if Year_1 <= future_year_dash:
        df2[f'AADT_1 {Year_1}'] = df2[f'AADT {present_year_dash}']*((1+(((df2[f'AADT {future_year_dash}']/df2[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_1 - present_year_dash))
    else:
        df2[f'AADT_1 {Year_1}'] = df2[f'AADT {future_year_dash}']*((1+(((df2[f'AADT {future_year_dash}']/df2[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_1 - future_year_dash))
    if Year_2 <= future_year_dash:
        df2[f'AADT_2 {Year_2}'] = df2[f'AADT {present_year_dash}']*((1+(((df2[f'AADT {future_year_dash}']/df2[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_2 - present_year_dash))
    else:
        df2[f'AADT_2 {Year_2}'] = df2[f'AADT {future_year_dash}']*((1+(((df2[f'AADT {future_year_dash}']/df2[f'AADT {present_year_dash}'])**(1/(future_year_dash-present_year_dash)))-1))**(Year_2 - future_year_dash))
    df2[f'AADT_1 {Year_1}'] = df2[f'AADT_1 {Year_1}'].astype(int)
    df2[f'AADT_2 {Year_2}'] = df2[f'AADT_2 {Year_2}'].astype(int)
    
    # Add commas to AADT values
    df2[f'AADT {present_year_dash}'] = df2[f'AADT {present_year_dash}'].apply(lambda x: '{:,.0f}'.format(float(x)) if pd.notnull(x) else '')
    df2[f'AADT {future_year_dash}'] = df2[f'AADT {future_year_dash}'].apply(lambda x: '{:,.0f}'.format(float(x)) if pd.notnull(x) else '')
    df2[f'AADT_1 {Year_1}'] = df2[f'AADT_1 {Year_1}'].apply(lambda x: '{:,.0f}'.format(float(x)) if pd.notnull(x) else '')
    df2[f'AADT_2 {Year_2}'] = df2[f'AADT_2 {Year_2}'].apply(lambda x: '{:,.0f}'.format(float(x)) if pd.notnull(x) else '')
    
    # Set the KDT columns to integers
    KDT_list = ['K Factor %', 'D Factor %', 'T Factor %']
    for KDT in KDT_list:
        df2[KDT] = pd.to_numeric(df2[KDT], errors='coerce')
        df2[KDT] = df2[KDT].fillna('-')
        df2[KDT] = df2[KDT].replace('-', 0)
        df2[KDT] = df2[KDT].round().astype(int)
    
    # Rename the projected AADT columns appropriately
    df2.rename(columns = {f'AADT {present_year_dash}':f'AADT {present_year_dash}',
                          f'AADT {future_year_dash}':f'AADT {future_year_dash}',
                          f'AADT_1 {Year_1}':f'Future AADT {Year_1}', 
                          f'AADT_2 {Year_2}':f'Future AADT {Year_2}'}, inplace = True)

    # Returns non-unique columns only, this cannot be overridden
    return df2.to_dict('records')


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
     State('year-2', 'value')],
)

# Downloads the table in CSV file format
def export_to_csv(n_clicks, present_year_dash, table_data, Route, BMP_value, EMP_value, Year_1, Year_2):
    # n_clicks prevents the unnecessary download as soon as the website opens
    if n_clicks > 0:
        df_export = pd.DataFrame.from_dict(table_data)

        # File name is based on selection route, BMP and EMP
        if Route is None:
            export_name = 'AADT-'+str(present_year_dash)+'-Table All-Routes BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
        else:
            export_name = 'AADT-'+str(present_year_dash)+'-Table '+str(Route)+' BMP-'+str(BMP_value)+' EMP-'+str(EMP_value)+' PY-'+str(Year_1)+'-'+str(Year_2)+'.csv'
        
        return dcc.send_data_frame(df_export.to_csv, export_name, index=False, encoding='utf-8-sig')
    

# End of dash app
if __name__ == '__main__':
    app.run(debug = True)
    
    
# Success print statement
print('\nMessage: Dashboard ready')