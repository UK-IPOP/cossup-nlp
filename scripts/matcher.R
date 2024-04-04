# install packages
# install.packages("readr", repos = "http://cran.us.r-project.org")
# install.packages("dplyr", repos = "http://cran.us.r-project.org")
# install.packages("MatchIt", repos = "http://cran.us.r-project.org")
# install.packages("tidyverse", repos = "http://cran.us.r-project.org")

# load packages
library(readr)
library(dplyr)
library(MatchIt)
library(tidyr)

# read csv
df <- read.csv("data/prepped/case_control_demographics.csv")

# match-it function
m2 <- matchit(case_control_category ~ age_category + race_category + gender_category + year_category, data = df, method = "nearest", distance = "glm", ratio = 2)

# match table
a <- match.data(m2)
a2 <- 
    a %>% 
    left_join(df %>% select(ccmeo_case)) %>% 
    select(matchnumber = subclass, ccmeo_case, age_category, race_category, gender_category, year_category, case_control_category, distance, weights) %>% 
    arrange(matchnumber, desc(case_control_category))
# write
write.csv(a2, "data/processed/matched_case_controls.csv", row.names = F)

