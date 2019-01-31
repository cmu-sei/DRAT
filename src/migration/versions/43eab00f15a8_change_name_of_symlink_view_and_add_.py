#------------------------------------------------------------------------------
# DRAT Prototype Tool Source Code
# 
# Copyright 2019 Carnegie Mellon University. All Rights Reserved.
# 
# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING 
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.
# 
# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.
# 
# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for non-US
# Government use and distribution.
# 
# This Software includes and/or makes use of the following Third-Party
# Software subject to its own license:
# 
# 1. Python 3.7 (https://docs.python.org/3/license.html)
# Copyright 2001-2019 Python Software Foundation.
# 
# 2. SQL Alchemy (https://github.com/sqlalchemy/sqlalchemy/blob/master/LICENSE)
# Copyright 2005-2019 SQLAlchemy authors and contributor.
# 
# DM19-0055
#------------------------------------------------------------------------------

"""Change name of symlink view and add mview

Revision ID: 43eab00f15a8
Revises: c211a0faa8d5
Create Date: 2018-08-20 09:01:04.033407

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43eab00f15a8'
down_revision = 'c211a0faa8d5'
branch_labels = None
depends_on = None

function_index = (
    """
CREATE INDEX file_detail_f01
  ON file_detail ( RESOLVE_SYMLINK ( file_location, file_target ) )
  WHERE ( ( file_type ) :: text = 'S' :: text );
    """
)

def upgrade():

    conn = op.get_bind()

    # Drop function-based index
    conn.execute(
        """
DROP INDEX file_detail_f01;
        """
    )

    # Rename view
    conn.execute(
        """
ALTER VIEW resolved_symlinks RENAME TO resolved_symlinks_vw;
        """
    )

    # Create materialized view
    conn.execute(
        """
CREATE MATERIALIZED VIEW resolved_symlinks AS
SELECT system_id
      ,file_detail_id
      ,prev_file_detail_id
      ,file_location
      ,file_target
      ,resolved_location
      ,target_type
  FROM resolved_symlinks_vw;
        """
    )

    # Recreate function index

    conn.execute(function_index)

    conn.execute(
        """
CREATE UNIQUE INDEX resolved_symlinks_u01 ON resolved_symlinks ( system_id, file_detail_id);
        """
    )


def downgrade():

    conn = op.get_bind()

    conn.execute("DROP INDEX file_detail_f01")
    conn.execute("DROP INDEX resolved_symlinks_u01")
    conn.execute("DROP MATERIALIZED VIEW resolved_symlinks")
    conn.execute(
        """
ALTER VIEW resolved_symlinks_vw RENAME TO resolved_symlinks;
        """
    )
    conn.execute(function_index)
