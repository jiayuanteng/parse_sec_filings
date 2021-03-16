#!/usr/bin/env python
# coding: utf-8
# industry search url https://www.sec.gov/cgi-bin/browse-edgar?SIC=4813

# import our libraries
import requests
import pandas as pd
from bs4 import BeautifulSoup
import sys, warnings




# url function
def make_url(base_url, comp):
    
    url = base_url
    
    # add each componet to the base url
    for r in comp:
        url = '{}/{}'.format(url, r)
        
    return url


# cik lookup table, search by ticker (capitalized, e.g. AAPL)
def cik_lookup(ticker):

    url = "https://www.sec.gov/files/company_tickers.json"

    decoded_content = requests.get(url).json()

    cik_to_ticker = []
    selected_cik_ticker_companyname = []

    for item in decoded_content:

        lookup_table = {}
        lookup_table['cik_number'] = decoded_content[item]["cik_str"]
        lookup_table['ticker'] = decoded_content[item]['ticker']
        lookup_table['company_name'] = decoded_content[item]['title']

        cik_to_ticker.append(lookup_table)

        if decoded_content[item]['ticker'] == ticker:

            selected_cik_ticker_companyname.append(lookup_table)

    if len(selected_cik_ticker_companyname) == 0:

        raise Exception("Ticker is not found")
    
    return cik_to_ticker, selected_cik_ticker_companyname


# Get the url of daily filings 

def get_daily_filing_url(yr):  # yr is a list of strings, e.g. ['2018','2019']
    
    # base url for the daily index files
    base_url = r"https://www.sec.gov/Archives/edgar/daily-index"

    for year in yr:
        
        # create the daily index url
        year_url = make_url(base_url, [year, 'index.json'])

        # request the url 
        decoded_content = requests.get(year_url).json()

        # create a master url list
        master_daily_filing_url = []

        # loop through the dictionary
        for item in decoded_content['directory']['item']:

            # create the url
            qtr_url = make_url(base_url, [year, item['name'], 'index.json'])


            # request url
            file_content= requests.get(qtr_url).json()


            for file in file_content['directory']['item']:

                if 'master' in file['name']:
                    file_url = make_url(base_url, [year, item['name'], file['name']])
                    master_daily_filing_url.append(file_url)

                    print('-'*100)
                    print('Pulling Daily Filings')
                    print(file_url)
                    
    return(master_daily_filing_url)

# Ger the url of filings for a specific company (search by cik)
def get_company_daily_filing_url(master_daily_filing_url, cik):
    
    
    company_daily_filing_url = []

    # loop through the master file url
    for file_url in master_daily_filing_url:

        # request that new content, this will not be a JSON STRUCTURE
        byte_data = requests.get(file_url).content

        # now that we loaded the data, we have a byte stream that needs to be decoded and then split by \n
        data = byte_data.decode('utf-8').split('\n')


         # finding the starting index
        for index, item in enumerate(data):

            if "CIK|Company Name|Form Type|Date Filed|File Name" in item:
                start_ind = index

        # create a new list that removes the junk and '-----'      
        data_format = data[start_ind + 2:]

        # loop through the data list 
        

        for index, item in enumerate(data_format):

            clean_item_data = item.split('|')
            
            if len(clean_item_data) == 0:
                
                print('No url stored')
            
            elif clean_item_data[0] == cik:
                
                clean_item_data[4] = "https://www.sec.gov/Archives/" + clean_item_data[4]
                
                company_daily_filing_url.append(clean_item_data)
        
                print('-'*100)
                print('Pulling company name')
                print(clean_item_data[1])
        

    for index, document in enumerate(company_daily_filing_url):

        # create a dictionary
        document_dict = {}
        document_dict['cik_number'] = document[0]
        document_dict['company_name'] = document[1]
        document_dict['form_id'] = document[2]
        document_dict['date'] = document[3]
        document_dict['file_url'] = document[4]

        company_daily_filing_url[index] = document_dict
     
    print('Done pulling url for {}'.format(company_daily_filing_url[0]['company_name']))

    return(company_daily_filing_url)


# Get the url of financial statements, default is 10-K

def get_company_fs_url(company_daily_filing_url, statement = "10-K"): 
    
    # only extract url of BS, IS, SCF, and stakeholder's equity
    # default is 10K
    
    index = 0
    
    filings_lists = []
    
    for filing_url in company_daily_filing_url:
       
        
        if filing_url['form_id'] == statement:
            
            documents_url = filing_url['file_url'].replace('-', '').replace('.txt','/index.json')
            
            index += 1
            
            
            if (index > 1 and statement == "10-K"): # warnings: more than one 10K found. This does not interrupt the program
                # raise(Exception('More than one 10-K available in {} for {}'.format(yr, filing_url['company_name'])))
                warnings.warn('More than one 10-K available for {}'.format(filing_url['company_name']))
   
            # request the url and decode it.
            content = requests.get(documents_url).json()

            for file in content['directory']['item']:
        
  
                # Grab the filing summary and create a new url leading to the file so we can download it.
                if file['name'] =='FilingSummary.xml':

                    xml_summary = 'https://www.sec.gov' + content['directory']['name'] + '/' + file['name']
            

                    print(xml_summary)

            # define a new base url that represents the filing folder. This will come in handy when we need to downlaod the reports.
            base_url = xml_summary.replace('FilingSummary.xml', '')

       
            # request and parse the content
            content = requests.get(xml_summary).content
            soup = BeautifulSoup(content, 'lxml')

            # find the 'myreports' tag because this contains all the individual reports submitted.
            reports = soup.find('myreports')

            # create the master list
            master_reports = []

            # loop through each report in the 'myreports' tag but avoid the last one as this will cause an error.
            for report in reports.find_all('report')[:-1]:

                # let's create a dictionary to store all the different parts we need.
                report_dict = {}
                report_dict['name_short'] = report.shortname.text
                report_dict['name_long'] = report.longname.text
                report_dict['position'] = report.position.text
                report_dict['category'] = report.menucategory.text
                report_dict['url'] = base_url +  report.htmlfilename.text

                # append the dictionary to the master list.
                master_reports.append(report_dict)

            # create the list to hold the statement urls
            statements_url = {}

            for report_dict in master_reports:

                # find the name of financial statements
                if ("consolidated" in report_dict['name_short'].lower() and "parenthetical" not in report_dict['name_short'].lower() and "comprehensive income" not in report_dict['name_short'].lower()):

                    if "balance sheets" in report_dict['name_short'].lower():
                        report_dict['name_short'] = "Balance Sheets"  
                    elif "statements of operations" in report_dict['name_short'].lower():
                        report_dict['name_short'] = "Income Statement"
                    elif "cash flows" in report_dict['name_short'].lower():
                        report_dict['name_short'] = "Statement of Cash Flow"
                    elif "stockholder" in report_dict['name_short'].lower():
                        report_dict['name_short'] = "Statement of of Stockholder's Equity"

                    # print some info and store it in the statements url.
                    print('-'*100)
                    print(report_dict['name_short'])
                    print(report_dict['url'])

                    statements_url[report_dict['name_short']] = report_dict['url']
        
            # store statements url (each year has 4 10-Qs)
            filings_lists.append(statements_url)
    
    if index == 0:
        raise Exception('Statement {} is not found'.format(statement))

    return(filings_lists)


# Parsing financial statements

def parsing_fs(filings_lists):
    
    filings_data = []
    
    # loop through each statement url
    for statements_url in filings_lists:
        
        # assume we want all the statements in a single data set
        statements_data = {}
        
        for num, statement in enumerate(statements_url):

            # define a dictionary that will store the different parts of the statement.
            statement_data = {}
            statement_data['headers'] = []
            statement_data['sections'] = []
            statement_data['data'] = []

            # request the statement file content
            content = requests.get(statements_url[statement]).content
            report_soup = BeautifulSoup(content, 'html')

            # find all the rows, figure out what type of row it is, parse the elements, and store in the statement file list.
            for index, row in enumerate(report_soup.table.find_all('tr')):

                # first let's get all the elements, does not include the column of footnote numbers, and footnote rows at the bottom of the table. Scraped the table save the rows where footnotes are as NaN
                cols = row.find_all('td', class_={'pl','text','num', 'nump'})

                # if it's a regular row and not a section or a table header
                if (len(row.find_all('th')) == 0 and len(row.find_all('strong')) == 0):
                    reg_row = [ele.text.strip() for ele in cols]
                    statement_data['data'].append(reg_row)

                # if it's a regular row and a section but not a table 
                elif (len(row.find_all('th')) == 0 and len(row.find_all('strong')) != 0):
                    sec_row = cols[0].text.strip()
                    statement_data['sections'].append(sec_row)

                # finally if it's not any of those it must be a header
                elif (len(row.find_all('th')) !=0):
                    hed_row = [ele.text.strip() for ele in row.find_all('th')]
                    statement_data['headers'].append(hed_row)

                else:
                    print ('We encountered an error.')

            # drop rows where footnotes are
            statement_data['data'] = [x for x in statement_data['data'] if x]

            # append it to the master list.
            statements_data[list(statements_url.keys())[num]] = statement_data 
            
        filings_data.append(statements_data)

    return(filings_data)


def covert_fs_to_df(statements_data, fs, fs_header): 
    
    data = statements_data[fs]['data']

    # Put the data in a DataFrame
    fs_df = pd.DataFrame(data) 

    # Define the Index column, rename it, and we need to make sure to drop the old column once we reindex.
    fs_df.index = fs_df[0]
    fs_df.index.name = 'Category'
    fs_df = fs_df.drop(0, axis = 1)


    # Get rid of the '$', '(', ')', and convert the '' to NaNs.
    fs_df = fs_df.replace('[\$,)]','', regex=True )\
    .replace( '[(]','-', regex=True)\
    .replace( '', 'NaN', regex=True)


    # everything is a string, so let's convert all the data to a float.
    # ifs_df = fs_df.astype(float)

    # Change the column headers
    assert(len(fs_df.columns) == len(fs_header))
    fs_df.columns = fs_header

    # Display
    print('-'*100)
    print('Final Product')
    print('-'*100)

    # show the df
    print(fs_df.head())

    return(fs_df)

